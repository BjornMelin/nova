#!/usr/bin/env python3
"""TypeScript SDK generation helpers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.release.sdk_common import (
    REPO_ROOT,
    GenerationTarget,
)

OPENAPI_TS_CLI = REPO_ROOT / "node_modules" / ".bin" / "openapi-ts"
OPENAPI_TS_CONFIG = REPO_ROOT / "openapi-ts.config.ts"
_LEGACY_TS_ARTIFACTS = (
    Path("src") / "client.ts",
    Path("src") / "errors.ts",
    Path("src") / "operations.ts",
    Path("src") / "types.ts",
    Path("src") / "generated",
)
_UPSTREAM_GET_PARSE_AS_SIGNATURE = (
    "export const getParseAs = (contentType: string | null): "
    "Exclude<Config['parseAs'], 'auto'> => {"
)
_COMPAT_GET_PARSE_AS_SIGNATURE = (
    "export const getParseAs = (contentType: string | null): "
    "Exclude<Config['parseAs'], 'auto'> | undefined => {"
)
# @hey-api/openapi-ts types SseFn with RequestOptions<never,...>, which forces
# onSseEvent to StreamEvent<never>. Align with MethodFn so TData flows to SSE
# callbacks and ServerSentEventsResult.
_SSE_FN_BROKEN_REQUEST_OPTIONS = (
    "Omit<RequestOptions<never, TResponseStyle, ThrowOnError>, 'method'>"
)
_SSE_FN_FIXED_REQUEST_OPTIONS = (
    "Omit<RequestOptions<TData, TResponseStyle, ThrowOnError>, 'method'>"
)
_GET_PARSE_AS_SIGNATURE_PATTERN = re.compile(
    r"export const getParseAs = \(contentType: string \| null\):\s*"
    r"Exclude<Config\[(?P<quote1>['\"])parseAs(?P=quote1)\],\s*"
    r"(?P<quote2>['\"])auto(?P=quote2)\s*>\s*"
    r"(?P<compat>\|\s*undefined\s*)?=>\s*{"
)
_SDK_OPERATION_DOCBLOCK_PATTERN = re.compile(
    r"/\*\*\n(?P<body>(?: \*.*\n)+?) \*/\nexport const (?P<name>\w+) =",
    re.MULTILINE,
)
# Google-style / FastAPI docstring sections excluded from public TSDoc.
_SDK_SERVER_DOC_SECTION_HEADER = re.compile(
    r"^(Args|Returns|Raises|Yields):\s*",
)
_SDK_FORBIDDEN_DOCBLOCK_TOKENS = ("Args:", "Returns:", "Raises:", "Yields:")
_SDK_OPTIONS_PARAM_DOC = (
    "@param options - request options including client, security, and request "
    "overrides."
)
_CLIENT_FETCH_TODO_COMMENT = (
    "    // TODO: we probably want to return error and improve types\n"
)
_GENERATED_TODO_PATTERN = re.compile(r"\b(?:TODO|FIXME|XXX)\b")


def _strip_ts_docblock_line(line: str) -> str:
    """Return the text after the leading `` * `` / `` *`` doc line prefix."""
    if line.startswith(" * "):
        return line[3:]
    if line.startswith(" *"):
        return line[2:].lstrip(" ") if len(line) > 2 else ""
    return line


def _sanitize_sdk_operation_docblock_body(body: str) -> str:
    """Remove server-only docstring sections from a captured TSDoc body.

    Strips paragraphs that begin with Python-style ``Args:`` / ``Returns:`` /
    ``Raises:`` / ``Yields:`` headings and their continuations (until a blank
    `` *`` line or the next section heading), leaving user-facing summary lines.
    """
    lines = body.splitlines()
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        content = _strip_ts_docblock_line(line)
        if _SDK_SERVER_DOC_SECTION_HEADER.match(content):
            index += 1
            while index < len(lines):
                inner = _strip_ts_docblock_line(lines[index])
                if inner == "":
                    index += 1
                    break
                if _SDK_SERVER_DOC_SECTION_HEADER.match(inner):
                    break
                index += 1
            continue
        out.append(line)
        index += 1
    return "\n".join(out) + ("\n" if body.endswith("\n") else "")


def _assert_sdk_docblock_body_sanitized(body: str) -> None:
    """Fail loudly if server-only headings leaked into SDK-facing TSDoc."""
    for token in _SDK_FORBIDDEN_DOCBLOCK_TOKENS:
        if token in body:
            raise RuntimeError(
                "TypeScript SDK operation docblock sanitization left forbidden "
                f"token {token!r} in docblock body:\n{body!r}"
            )


_UNDOCUMENTED_TYPE_EXPORT_PATTERN = re.compile(
    r"(?m)^(?P<export>export type (?P<name>[A-Z][A-Za-z0-9]+) = )"
)
_TYPE_ALIAS_SUMMARY_OVERRIDES = {
    "HttpValidationError": (
        "Validation error envelope returned for invalid request payloads."
    ),
    "ReadinessChecks": "Canonical live traffic gates reported by readiness.",
    "ValidationError": (
        "One request-validation issue with location, message, and error type."
    ),
}


def _type_alias_summary(name: str) -> str | None:
    """Return a sentence-style summary for generated exported type aliases."""
    override = _TYPE_ALIAS_SUMMARY_OVERRIDES.get(name)
    if override is not None:
        return override
    if name.endswith("Data"):
        operation_name = name.removesuffix("Data")
        return f"Request data for the `{operation_name}` operation."
    if name.endswith("Errors"):
        operation_name = name.removesuffix("Errors")
        return f"Error responses for the `{operation_name}` operation."
    if name.endswith("Error"):
        operation_name = name.removesuffix("Error")
        return f"Error union for the `{operation_name}` operation."
    if name.endswith("Responses"):
        operation_name = name.removesuffix("Responses")
        return f"Response variants for the `{operation_name}` operation."
    if name.endswith("Response"):
        operation_name = name.removesuffix("Response")
        return f"Response union for the `{operation_name}` operation."
    return None


def _snake_to_pascal(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("_"))


def _snake_to_camel(value: str) -> str:
    pascal = _snake_to_pascal(value)
    return pascal[:1].lower() + pascal[1:]


def _sentence(text: str) -> str:
    normalized = " ".join(text.split()).strip()
    if not normalized:
        return normalized
    return normalized if normalized.endswith(".") else f"{normalized}."


def _ts_docblock(indent: str, *, summary: str, description: str | None) -> str:
    lines = ["/**", f" * {_sentence(summary)}"]
    if description:
        lines.extend([" *", f" * {_sentence(description)}"])
    lines.append(" */")
    return "\n".join(f"{indent}{line}" for line in lines)


def _extract_success_response_description(
    operation: dict[str, Any],
) -> str | None:
    responses = operation.get("responses")
    if not isinstance(responses, dict):
        return None
    for status_code in ("200", "201", "202", "204"):
        response = responses.get(status_code)
        if not isinstance(response, dict):
            continue
        description = response.get("description")
        if isinstance(description, str) and description.strip():
            return description.strip()
    return None


def _operation_docs_by_export_name(
    spec: dict[str, Any],
) -> dict[str, dict[str, str]]:
    docs: dict[str, dict[str, str]] = {}
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return docs
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            summary = operation.get("summary")
            if not isinstance(operation_id, str) or not isinstance(
                summary, str
            ):
                continue
            description = operation.get("description")
            docs[_snake_to_camel(operation_id)] = {
                "summary": summary.strip(),
                "description": (
                    description.strip()
                    if isinstance(description, str) and description.strip()
                    else ""
                ),
                "returns": (
                    _extract_success_response_description(operation)
                    or (
                        "The response from the "
                        f"`{_snake_to_camel(operation_id)}` operation."
                    )
                ),
            }
    return docs


def _schema_property_docs(
    spec: dict[str, Any],
) -> dict[str, dict[str, str]]:
    docs: dict[str, dict[str, str]] = {}
    components = spec.get("components")
    if not isinstance(components, dict):
        return docs
    schemas = components.get("schemas")
    if not isinstance(schemas, dict):
        return docs
    for schema_name, schema in schemas.items():
        if not isinstance(schema_name, str) or not isinstance(schema, dict):
            continue
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            continue
        property_docs = {
            property_name: description.strip()
            for property_name, property_schema in properties.items()
            if isinstance(property_name, str)
            and isinstance(property_schema, dict)
            and isinstance(
                (description := property_schema.get("description")), str
            )
            and description.strip()
        }
        if property_docs:
            docs[schema_name] = property_docs
    return docs


def _operation_data_property_docs(
    spec: dict[str, Any],
) -> dict[str, dict[str, dict[str, str]]]:
    docs: dict[str, dict[str, dict[str, str]]] = {}
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return docs
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str):
                continue
            alias = f"{_snake_to_pascal(operation_id)}Data"
            parameter_docs: dict[str, dict[str, str]] = {}
            for parameter in operation.get("parameters", []):
                if not isinstance(parameter, dict):
                    continue
                location = parameter.get("in")
                name = parameter.get("name")
                description = parameter.get("description")
                if not isinstance(location, str) or not isinstance(name, str):
                    continue
                if not isinstance(description, str) or not description.strip():
                    continue
                parameter_docs.setdefault(location, {})[name] = (
                    description.strip()
                )
            if parameter_docs:
                docs[alias] = parameter_docs
    return docs


def _replace_property_docblock(
    lines: list[str],
    *,
    index: int,
    indent: str,
    description: str,
) -> list[str]:
    docblock = _ts_docblock(indent, summary=description, description=None)
    docblock_lines = docblock.splitlines()
    start = index
    while start > 0 and lines[start - 1].startswith(f"{indent}/**"):
        start -= 1
        break
    if start > 0 and lines[start - 1].startswith(f"{indent} *"):
        while start > 0 and lines[start - 1].startswith(f"{indent} *"):
            start -= 1
        if start > 0 and lines[start - 1].startswith(f"{indent}/**"):
            start -= 1
    end = index
    if start < index and lines[start].startswith(f"{indent}/**"):
        end = start
        while end < index and not lines[end].startswith(f"{indent} */"):
            end += 1
        if end < len(lines):
            end += 1
        return lines[:start] + docblock_lines + lines[end:]
    return lines[:index] + docblock_lines + lines[index:]


def _apply_property_docs_at_indent(
    lines: list[str],
    *,
    property_docs: dict[str, str],
    indent: str,
) -> list[str]:
    property_pattern = re.compile(
        rf"^{re.escape(indent)}(?P<name>'[^']+'|[A-Za-z_][\w-]*)\??:"
    )
    index = 0
    while index < len(lines):
        match = property_pattern.match(lines[index])
        if match is None:
            index += 1
            continue
        property_name = match.group("name").strip("'")
        description = property_docs.get(property_name)
        if description:
            lines = _replace_property_docblock(
                lines,
                index=index,
                indent=indent,
                description=description,
            )
            index += 1
            continue
        index += 1
    return lines


def _apply_operation_data_docs(
    block_lines: list[str],
    *,
    property_docs: dict[str, dict[str, str]],
) -> list[str]:
    section_pattern = re.compile(
        r"^    (?P<section>headers|path|query)\??: \{$"
    )
    index = 0
    while index < len(block_lines):
        match = section_pattern.match(block_lines[index])
        if match is None:
            index += 1
            continue
        section = match.group("section")
        nested_docs = property_docs.get(section)
        if not nested_docs:
            index += 1
            continue
        end = index + 1
        while end < len(block_lines) and block_lines[end] != "    };":
            end += 1
        if end >= len(block_lines):
            break
        nested_lines = _apply_property_docs_at_indent(
            block_lines[index + 1 : end],
            property_docs=nested_docs,
            indent="        ",
        )
        block_lines = (
            block_lines[: index + 1] + nested_lines + block_lines[end:]
        )
        index = end
    return block_lines


def _apply_typescript_reference_doc_repairs(
    root: Path,
    *,
    spec: dict[str, Any],
) -> None:
    operation_docs = _operation_docs_by_export_name(spec)
    sdk_path = root / "sdk.gen.ts"
    if sdk_path.exists():
        sdk_text = sdk_path.read_text(encoding="utf-8")

        def _rewrite_operation_docblock(match: re.Match[str]) -> str:
            export_name = match.group("name")
            details = operation_docs.get(export_name)
            if details is None:
                return match.group(0)
            lines = [
                "/**",
                f" * {_sentence(details['summary'])}",
            ]
            if details["description"]:
                lines.extend([" *", f" * {_sentence(details['description'])}"])
            lines.extend(
                [
                    " *",
                    f" * {_SDK_OPTIONS_PARAM_DOC}",
                    f" * @returns {_sentence(details['returns'])}",
                    " */",
                ]
            )
            return "\n".join(lines) + "\n" + f"export const {export_name} ="

        updated_sdk_text = _SDK_OPERATION_DOCBLOCK_PATTERN.sub(
            _rewrite_operation_docblock,
            sdk_text,
        )
        if updated_sdk_text != sdk_text:
            sdk_path.write_text(updated_sdk_text, encoding="utf-8")

    types_path = root / "types.gen.ts"
    if not types_path.exists():
        return

    source = types_path.read_text(encoding="utf-8")
    lines = source.splitlines()
    schema_docs = _schema_property_docs(spec)
    operation_data_docs = _operation_data_property_docs(spec)
    result: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"export type (?P<name>[A-Za-z0-9_]+) = \{$", line)
        if match is None:
            result.append(line)
            index += 1
            continue
        type_name = match.group("name")
        block_lines = [line]
        index += 1
        depth = 1
        while index < len(lines):
            block_line = lines[index]
            block_lines.append(block_line)
            depth += block_line.count("{")
            depth -= block_line.count("}")
            index += 1
            if depth == 0:
                break
        inner_lines = block_lines[1:-1]
        if type_name in schema_docs:
            inner_lines = _apply_property_docs_at_indent(
                inner_lines,
                property_docs=schema_docs[type_name],
                indent="    ",
            )
        elif type_name in operation_data_docs:
            inner_lines = _apply_operation_data_docs(
                inner_lines,
                property_docs=operation_data_docs[type_name],
            )
        result.extend([block_lines[0], *inner_lines, block_lines[-1]])
    updated_source = "\n".join(result) + "\n"
    if updated_source != source:
        types_path.write_text(updated_source, encoding="utf-8")


def _ensure_typescript_type_docblocks(source: str) -> str:
    """Add sentence-style docblocks to exported TS type aliases."""
    for name, summary in _TYPE_ALIAS_SUMMARY_OVERRIDES.items():
        titles = {name, name.upper()}
        if name == "HttpValidationError":
            titles.add("HTTPValidationError")
        for title in titles:
            source = source.replace(
                f"/**\n * {title}\n *\n * {summary}\n */\nexport type {name} =",
                f"/**\n * {summary}\n */\nexport type {name} =",
            )
            source = source.replace(
                f"/**\n * {title}\n */\nexport type {name} =",
                f"/**\n * {summary}\n */\nexport type {name} =",
            )
    result: list[str] = []
    pending_docblock: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("/**") or pending_docblock:
            pending_docblock.append(line)
            if stripped.endswith("*/"):
                result.extend(pending_docblock)
                pending_docblock = []
            continue
        match = _UNDOCUMENTED_TYPE_EXPORT_PATTERN.match(line)
        if match:
            alias_summary = _type_alias_summary(match.group("name"))
            previous_non_empty = next(
                (entry.strip() for entry in reversed(result) if entry.strip()),
                "",
            )
            if alias_summary is not None and previous_non_empty != "*/":
                result.extend(
                    [
                        "/**",
                        f" * {alias_summary}",
                        " */",
                    ]
                )
        result.append(line)
    return "\n".join(result) + "\n"


_READINESS_CHECKS_TYPE_LINES = [
    "/**",
    " * Canonical live traffic gates reported by readiness.",
    " */",
    "export type ReadinessChecks = {",
    "    /**",
    "     * Whether the activity store is reachable for diagnostic rollups.",
    "     */",
    "    activity_store: boolean;",
    "    /**",
    "     * Whether the configured bearer-token verifier can currently",
    "     * resolve signing keys.",
    "     */",
    "    auth_dependency: boolean;",
    "    /**",
    "     * Whether the export publisher and export repository are ready.",
    "     */",
    "    export_runtime: boolean;",
    "    /**",
    "     * Whether the idempotency store is reachable when idempotency",
    "     * is enabled.",
    "     */",
    "    idempotency_store: boolean;",
    "    /**",
    "     * Whether transfer persistence and the configured S3 bucket",
    "     * are ready.",
    "     */",
    "    transfer_runtime: boolean;",
    "};",
]

_READINESS_RESPONSE_TYPE_LINES = [
    "/**",
    " * ReadinessResponse",
    " *",
    " * Readiness endpoint response body.",
    " */",
    "export type ReadinessResponse = {",
    "    /**",
    "     * Canonical live traffic-gate results.",
    "     */",
    "    checks: ReadinessChecks;",
    "    /**",
    "     * Whether every required traffic dependency is ready.",
    "     */",
    "    ok: boolean;",
    "};",
]


def _drop_trailing_docblock(lines: list[str]) -> None:
    """Remove the docblock immediately preceding a rewritten export."""
    index = len(lines) - 1
    while index >= 0 and lines[index] == "":
        index -= 1
    if index < 0 or lines[index].strip() != "*/":
        return
    start = index
    while start >= 0 and lines[start].strip() != "/**":
        start -= 1
    if start < 0:
        return
    del lines[start : index + 1]
    while lines and lines[-1] == "":
        lines.pop()


def _rewrite_explicit_readiness_types(source: str) -> str:
    """Normalize generated readiness types to the canonical fixed schema."""
    if "export type ReadinessChecks = {" in source and (
        "checks: ReadinessChecks;" in source
    ):
        return source

    lines = source.splitlines()
    result: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line != "export type ReadinessResponse = {":
            result.append(line)
            index += 1
            continue

        block_lines = [line]
        index += 1
        depth = 1
        while index < len(lines):
            block_line = lines[index]
            block_lines.append(block_line)
            depth += block_line.count("{")
            depth -= block_line.count("}")
            index += 1
            if depth == 0:
                break

        block_text = "\n".join(block_lines)
        if "[key: string]: boolean;" not in block_text:
            result.extend(block_lines)
            continue

        _drop_trailing_docblock(result)
        if result and result[-1] != "":
            result.append("")
        result.extend(_READINESS_CHECKS_TYPE_LINES)
        result.append("")
        result.extend(_READINESS_RESPONSE_TYPE_LINES)

    updated = "\n".join(result)
    return updated + ("\n" if source.endswith("\n") else "")


def _apply_typescript_upstream_compatibility_fixes(root: Path) -> None:
    """Apply narrow compatibility fixes for current upstream TS output.

    Args:
        root: Root directory containing generated client files.

    Raises:
        RuntimeError: Raised when the expected upstream ``getParseAs``
            signature is missing from the generated output.
    """
    client_types_path = root / "client" / "types.gen.ts"
    if client_types_path.exists():
        ct_text = client_types_path.read_text(encoding="utf-8")
        if _SSE_FN_BROKEN_REQUEST_OPTIONS in ct_text:
            ct_text = ct_text.replace(
                _SSE_FN_BROKEN_REQUEST_OPTIONS,
                _SSE_FN_FIXED_REQUEST_OPTIONS,
                1,
            )
            client_types_path.write_text(ct_text, encoding="utf-8")

    utils_path = root / "client" / "utils.gen.ts"
    if not utils_path.exists():
        return

    text = utils_path.read_text(encoding="utf-8")
    if _COMPAT_GET_PARSE_AS_SIGNATURE in text:
        pass  # Already patched; keep normalizing other generated files.
    elif _UPSTREAM_GET_PARSE_AS_SIGNATURE in text:
        updated = text.replace(
            _UPSTREAM_GET_PARSE_AS_SIGNATURE,
            _COMPAT_GET_PARSE_AS_SIGNATURE,
            1,
        )
        if updated != text:
            utils_path.write_text(updated, encoding="utf-8")
    else:
        match = _GET_PARSE_AS_SIGNATURE_PATTERN.search(text)
        if match is None:
            raise RuntimeError(
                "unexpected generated TypeScript SDK output: "
                "missing recognizable getParseAs signature in "
                f"{utils_path}"
            )
        if match.group("compat") is None:
            updated = (
                text[: match.start()]
                + _COMPAT_GET_PARSE_AS_SIGNATURE
                + text[match.end() :]
            )
            if updated != text:
                utils_path.write_text(updated, encoding="utf-8")

    for client_path in (
        root / "client.gen.ts",
        root / "client" / "client.gen.ts",
    ):
        if not client_path.exists():
            continue
        client_text = client_path.read_text(encoding="utf-8")
        if _CLIENT_FETCH_TODO_COMMENT in client_text:
            client_text = client_text.replace(_CLIENT_FETCH_TODO_COMMENT, "", 1)
            client_path.write_text(client_text, encoding="utf-8")

    sdk_path = root / "sdk.gen.ts"
    if sdk_path.exists():
        sdk_text = sdk_path.read_text(encoding="utf-8")

        def _normalize_docblock(match: re.Match[str]) -> str:
            operation_name = match.group("name")
            body = match.group("body")
            body = _sanitize_sdk_operation_docblock_body(body)
            _assert_sdk_docblock_body_sanitized(body)
            normalized_lines = body.splitlines()
            for index, line in enumerate(normalized_lines):
                stripped = line.removeprefix(" * ").strip()
                if stripped and stripped != "*" and not stripped.endswith("."):
                    normalized_lines[index] = f" * {stripped}."
                    break
            if not any("@param options" in line for line in normalized_lines):
                if normalized_lines and normalized_lines[-1] != " *":
                    normalized_lines.append(" *")
                normalized_lines.append(f" * {_SDK_OPTIONS_PARAM_DOC}")
            if "@returns" not in body:
                if normalized_lines and normalized_lines[-1] != " *":
                    normalized_lines.append(" *")
                normalized_lines.append(
                    " * @returns The response from the "
                    f"`{operation_name}` operation."
                )
            return (
                "/**\n" + "\n".join(normalized_lines) + "\n"
                " */\n"
                f"export const {operation_name} ="
            )

        normalized_sdk_text = _SDK_OPERATION_DOCBLOCK_PATTERN.sub(
            _normalize_docblock,
            sdk_text,
        )
        if normalized_sdk_text != sdk_text:
            sdk_path.write_text(normalized_sdk_text, encoding="utf-8")

    types_path = root / "types.gen.ts"
    if types_path.exists():
        types_text = types_path.read_text(encoding="utf-8")
        normalized_types_text = _rewrite_explicit_readiness_types(types_text)
        normalized_types_text = _ensure_typescript_type_docblocks(
            normalized_types_text
        )
        if normalized_types_text != types_text:
            types_path.write_text(normalized_types_text, encoding="utf-8")


def _run_openapi_ts(
    *,
    input_spec_path: Path,
    output_path: Path,
) -> None:
    """Run the @hey-api/openapi-ts generator for the provided OpenAPI spec.

    Args:
        input_spec_path: Path to the generated public OpenAPI JSON file.
        output_path: Path where the TypeScript SDK output directory should be
            written.

    Raises:
        RuntimeError: Raised when the `openapi-ts` CLI binary is missing at
            ``OPENAPI_TS_CLI``.
        RuntimeError: Raised when the committed
            ``OPENAPI_TS_CONFIG`` file is missing.
        RuntimeError: Raised when the command invocation fails because
            `npm` is unavailable or not on ``PATH`` (wrapped
            `FileNotFoundError`).
        RuntimeError: Raised when generation exceeds the 120-second timeout
            (`subprocess.TimeoutExpired`) and includes captured stdout/stderr
            details.
        RuntimeError: Raised when the command exits non-zero and includes
            captured stdout/stderr details in the message.
    """
    if not OPENAPI_TS_CLI.exists():
        raise RuntimeError(
            "@hey-api/openapi-ts generation failed: missing repo-installed "
            f"CLI at {OPENAPI_TS_CLI}; run `npm ci` from repo root"
        )
    if not OPENAPI_TS_CONFIG.exists():
        raise RuntimeError(
            f"missing committed openapi-ts config at {OPENAPI_TS_CONFIG}"
        )

    command = ["npm", "run", "openapi-ts"]
    env = os.environ | {
        "NOVA_OPENAPI_TS_INPUT": str(input_spec_path),
        "NOVA_OPENAPI_TS_OUTPUT": str(output_path),
    }
    try:
        result = subprocess.run(  # noqa: S603
            command,
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
            timeout=120,
            env=env,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "@hey-api/openapi-ts generation failed: unable to invoke "
            f"command {' '.join(command)}; ensure Node/npm are installed "
            "and that `npm` is available on PATH"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.strip()
            if isinstance(exc.stdout, str)
            else str(exc.stdout or "").strip()
        )
        stderr = (
            exc.stderr.strip()
            if isinstance(exc.stderr, str)
            else str(exc.stderr or "").strip()
        )
        details = stderr or stdout or "no output captured"
        raise RuntimeError(
            "@hey-api/openapi-ts generation timed out after 120s for "
            f"{input_spec_path} using command {' '.join(command)}: {details}"
        ) from exc
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or "no output captured"
        raise RuntimeError(
            "@hey-api/openapi-ts generation command failed for "
            f"{input_spec_path}: {details}"
        )


def _typescript_generated_files(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _assert_no_generated_todo_markers(root: Path) -> None:
    """Fail when generated TS output still contains unresolved TODO markers."""
    findings: list[str] = []
    for relative_path, content in _typescript_generated_files(root).items():
        for line_number, line in enumerate(content.splitlines(), start=1):
            if _GENERATED_TODO_PATTERN.search(line):
                findings.append(
                    f"{relative_path}:{line_number}: {line.strip()}"
                )
    if findings:
        joined = "\n".join(findings)
        raise RuntimeError(
            "generated TypeScript SDK output contains unresolved TODO "
            f"markers:\n{joined}"
        )


def _check_typescript_generated_output(
    package_root: Path,
    *,
    expected_root: Path,
) -> list[str]:
    issues: list[str] = []
    actual_root = package_root / "src" / "client"
    if not actual_root.exists():
        issues.append(f"missing generated SDK directory: {actual_root}")
        return issues

    expected_files = _typescript_generated_files(expected_root)
    actual_files = _typescript_generated_files(actual_root)
    missing = sorted(set(expected_files) - set(actual_files))
    extra = sorted(set(actual_files) - set(expected_files))
    stale = sorted(
        path
        for path in expected_files
        if path in actual_files and actual_files[path] != expected_files[path]
    )
    if missing:
        issues.append(
            "missing expected generated SDK artifacts in "
            f"{actual_root}: {', '.join(missing)}"
        )
    if extra:
        issues.append(
            "unexpected generated SDK artifacts in "
            f"{actual_root}: {', '.join(extra)}"
        )
    issues.extend(
        f"stale generated client artifact: {actual_root / rel_path}"
        for rel_path in stale
    )

    for legacy_path in _LEGACY_TS_ARTIFACTS:
        absolute_path = package_root / legacy_path
        if absolute_path.exists():
            issues.append(
                "obsolete TypeScript SDK artifact still present: "
                f"{absolute_path}"
            )
    return issues


def _remove_legacy_typescript_artifacts(package_root: Path) -> None:
    for legacy_path in _LEGACY_TS_ARTIFACTS:
        absolute_path = package_root / legacy_path
        if absolute_path.is_dir():
            shutil.rmtree(absolute_path)
        elif absolute_path.exists():
            absolute_path.unlink()


def generate_or_check_typescript_sdk(
    target: GenerationTarget,
    *,
    spec: dict[str, Any],
    check: bool,
) -> list[str]:
    """Generate or verify the committed TypeScript SDK tree.

    Args:
        target: Generation target containing the TypeScript package root.
        spec: OpenAPI specification object, serialized and reduced to the public
            spec before SDK generation.
        check: If ``True``, compare generated output with committed artifacts
            and return mismatches; if ``False``, replace committed SDK output.

    Returns:
        A list of mismatched file/path entries when ``check`` is ``True``;
            otherwise an empty list.

    Raises:
        OSError: Raised by ``tempfile`` or file-system write/read operations.
        (TypeError, ValueError): Raised on JSON serialization or decoding
            failures.
        RuntimeError: Raised from ``_run_openapi_ts`` if generation
            prerequisites or command execution fail.
        OSError: Raised by ``shutil`` operations when copying/removing
            artifacts.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        input_spec_path = tmp_root / "nova-file-api.public.openapi.json"
        output_path = tmp_root / "client"
        input_spec_path.write_text(
            json.dumps(spec, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _run_openapi_ts(
            input_spec_path=input_spec_path, output_path=output_path
        )
        _apply_typescript_upstream_compatibility_fixes(output_path)
        _apply_typescript_reference_doc_repairs(
            output_path,
            spec=spec,
        )
        _assert_no_generated_todo_markers(output_path)

        if check:
            return _check_typescript_generated_output(
                target.ts_package_root,
                expected_root=output_path,
            )

        package_root = target.ts_package_root
        generated_root = package_root / "src" / "client"
        shutil.rmtree(generated_root, ignore_errors=True)
        generated_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(output_path, generated_root)
        _remove_legacy_typescript_artifacts(package_root)
        shutil.rmtree(package_root / "dist", ignore_errors=True)
    return []
