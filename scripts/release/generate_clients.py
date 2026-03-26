#!/usr/bin/env python3
# ruff: noqa: E501
"""Generate public TypeScript and R SDK artifacts from committed OpenAPI."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from nova_runtime_support import (
    SDK_VISIBILITY_EXTENSION,
    SDK_VISIBILITY_INTERNAL,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_ROOT = REPO_ROOT / "packages" / "contracts" / "openapi"
HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head")
OPENAPI_TYPESCRIPT_CLI = (
    REPO_ROOT / "node_modules" / ".bin" / "openapi-typescript"
)
_PARAM_SEGMENT = re.compile(r"^{([^{}]+)}$")
_NON_IDENTIFIER = re.compile(r"[^a-z0-9]+")
_VALID_IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


@dataclass(frozen=True)
class OperationParameter:
    """Single OpenAPI parameter carried into generated client surfaces."""

    name: str
    required: bool


@dataclass(frozen=True)
class Operation:
    """Single public OpenAPI operation used for generated client artifacts."""

    operation_id: str
    method: str
    path: str
    summary: str | None
    has_request_body: bool
    has_required_request_body: bool
    path_parameters: tuple[OperationParameter, ...]
    query_parameters: tuple[OperationParameter, ...]
    has_header_params: bool
    has_required_header_params: bool
    request_content_types: tuple[str, ...]
    response_status_codes: tuple[int, ...]

    @property
    def has_path_params(self) -> bool:
        """Return whether the operation declares any path parameters."""
        return len(self.path_parameters) > 0

    @property
    def has_query_params(self) -> bool:
        """Return whether the operation declares any query parameters."""
        return len(self.query_parameters) > 0

    @property
    def has_required_query_params(self) -> bool:
        """Return whether any declared query parameter is required."""
        return any(parameter.required for parameter in self.query_parameters)

    @property
    def type_base_name(self) -> str:
        """Return the PascalCase type prefix for the operation."""
        return "".join(
            part.capitalize() for part in self.operation_id.split("_")
        )

    @property
    def request_type_name(self) -> str:
        """Return the request-options type name for the operation."""
        return f"{self.type_base_name}RequestOptions"

    @property
    def requires_request(self) -> bool:
        """Return whether the generated client method must take a request object."""
        return (
            (self.has_request_body and self.has_required_request_body)
            or self.has_path_params
            or self.has_required_query_params
            or self.has_required_header_params
        )

    @property
    def default_request_content_type(self) -> str | None:
        """Return the only request content type when there is exactly one."""
        if len(self.request_content_types) != 1:
            return None
        return self.request_content_types[0]


@dataclass(frozen=True)
class GenerationTarget:
    """Output targets for one committed OpenAPI document."""

    spec_path: Path
    package_name: str
    ts_package_root: Path
    client_factory_name: str
    client_interface_name: str
    client_options_name: str
    r_package_name: str
    r_package_title: str
    r_package_description: str
    r_output_path: Path
    r_client_output_path: Path
    r_client_prefix: str
    catalog_function_name: str


TARGETS = (
    GenerationTarget(
        spec_path=OPENAPI_ROOT / "nova-file-api.openapi.json",
        package_name="@nova/sdk-file",
        ts_package_root=REPO_ROOT / "packages" / "nova_sdk_file",
        client_factory_name="createNovaFileClient",
        client_interface_name="NovaFileClient",
        client_options_name="NovaFileClientOptions",
        r_package_name="nova.sdk.r.file",
        r_package_title="Nova SDK R file client",
        r_package_description="Generated R client for the Nova file API.",
        r_output_path=REPO_ROOT
        / "packages"
        / "nova_sdk_r_file"
        / "R"
        / "generated.R",
        r_client_output_path=REPO_ROOT
        / "packages"
        / "nova_sdk_r_file"
        / "R"
        / "client.R",
        r_client_prefix="nova_file",
        catalog_function_name="nova_file_operation_catalog",
    ),
)

_R_PACKAGE_MAINTAINER = (
    'person("Nova SDK Team", email = "sdk@nova.invalid", '
    'role = c("aut", "cre"))'
)
_DEFAULT_R_PACKAGE_VERSION = "0.1.0"


def _load_spec(spec_path: Path) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(spec_path.read_text(encoding="utf-8")),
    )


def _load_operations(spec_path: Path) -> tuple[dict[str, Any], list[Operation]]:
    spec = _load_spec(spec_path)
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise TypeError(f"OpenAPI spec missing paths object: {spec_path}")

    operations: list[Operation] = []
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, dict):
            continue
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            if (
                operation.get(SDK_VISIBILITY_EXTENSION)
                == SDK_VISIBILITY_INTERNAL
            ):
                continue

            operation_id = operation.get(
                "operationId"
            ) or _default_operation_id(
                method=method,
                path=path,
            )
            summary = operation.get("summary")
            parameter_index = _collect_parameters(spec, path_item, operation)
            response_status_codes = tuple(
                sorted(_collect_response_status_codes(operation))
            )
            operations.append(
                Operation(
                    operation_id=str(operation_id),
                    method=method.upper(),
                    path=path,
                    summary=str(summary) if summary else None,
                    has_request_body=_has_request_body(spec, operation),
                    has_required_request_body=_request_body_required(
                        spec, operation
                    ),
                    path_parameters=_collect_operation_parameters(
                        parameter_index.get("path", ())
                    ),
                    query_parameters=_collect_operation_parameters(
                        parameter_index.get("query", ())
                    ),
                    has_header_params=("header" in parameter_index),
                    has_required_header_params=_parameter_group_has_required(
                        parameter_index.get("header", ()),
                    ),
                    request_content_types=_collect_request_content_types(
                        spec, operation
                    ),
                    response_status_codes=response_status_codes,
                )
            )
    operations.sort(
        key=lambda item: (item.path, item.method, item.operation_id)
    )
    _assert_unique_operation_ids(spec_path=spec_path, operations=operations)
    return spec, operations


def _default_operation_id(*, method: str, path: str) -> str:
    stripped = path.strip("/")
    if not stripped:
        return f"{method.lower()}_root"
    parts: list[str] = []
    for segment in stripped.split("/"):
        match = _PARAM_SEGMENT.fullmatch(segment)
        if match is not None:
            param_name = _normalize_identifier(match.group(1)) or "param"
            parts.append(f"by_{param_name}")
            continue
        normalized = _normalize_identifier(segment)
        if normalized:
            parts.append(normalized)
    suffix = "_".join(parts) if parts else "root"
    return f"{method.lower()}_{suffix}"


def _normalize_identifier(value: str) -> str:
    lowered = value.strip().lower()
    return _NON_IDENTIFIER.sub("_", lowered).strip("_")


def _collect_parameters(
    spec: dict[str, Any],
    path_item: dict[str, Any],
    operation: dict[str, Any],
) -> dict[str, tuple[dict[str, Any], ...]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for source in (
        path_item.get("parameters", []),
        operation.get("parameters", []),
    ):
        if not isinstance(source, list):
            continue
        for raw_parameter in source:
            parameter = _resolve_parameter(spec, raw_parameter)
            param_in = str(parameter.get("in", "")).strip()
            param_name = str(parameter.get("name", "")).strip()
            if not param_in or not param_name:
                continue
            merged[(param_in, param_name)] = parameter

    grouped: dict[str, list[dict[str, Any]]] = {}
    for (param_in, _), parameter in merged.items():
        grouped.setdefault(param_in, []).append(parameter)

    return {
        param_in: tuple(
            sorted(group, key=lambda item: str(item.get("name", "")))
        )
        for param_in, group in grouped.items()
    }


def _resolve_parameter(
    spec: dict[str, Any],
    raw_parameter: Any,
) -> dict[str, Any]:
    if not isinstance(raw_parameter, dict):
        return {}
    ref = raw_parameter.get("$ref")
    if ref is None:
        return raw_parameter
    if not isinstance(ref, str) or not ref.startswith(
        "#/components/parameters/"
    ):
        raise ValueError(f"Unsupported parameter reference: {ref!r}")
    parameter_name = ref.rsplit("/", 1)[-1]
    components = spec.get("components", {})
    parameters = (
        components.get("parameters", {}) if isinstance(components, dict) else {}
    )
    resolved = (
        parameters.get(parameter_name) if isinstance(parameters, dict) else None
    )
    if not isinstance(resolved, dict):
        raise TypeError(f"Missing component parameter for reference: {ref}")
    return resolved


def _resolve_request_body(
    spec: dict[str, Any],
    operation: dict[str, Any],
) -> dict[str, Any] | None:
    request_body = operation.get("requestBody")
    if not isinstance(request_body, dict):
        return None
    return _resolve_request_body_definition(spec, request_body)


def _resolve_request_body_definition(
    spec: dict[str, Any],
    request_body: dict[str, Any],
    *,
    seen_refs: frozenset[str] | None = None,
) -> dict[str, Any]:
    seen_refs_set = set(seen_refs or ())
    ref = request_body.get("$ref")
    if isinstance(ref, str):
        if not ref.startswith("#/"):
            raise ValueError(f"Unsupported requestBody reference: {ref!r}")
        if ref in seen_refs_set:
            raise ValueError(f"Circular requestBody reference detected: {ref}")
        seen_refs_set.add(ref)
        resolved = _resolve_local_ref(spec, ref)
        if not isinstance(resolved, dict):
            raise TypeError(
                f"requestBody reference did not resolve to an object: {ref}"
            )
        return _resolve_request_body_definition(
            spec,
            resolved,
            seen_refs=frozenset(seen_refs_set),
        )
    return request_body


def _has_request_body(spec: dict[str, Any], operation: dict[str, Any]) -> bool:
    return _resolve_request_body(spec, operation) is not None


def _request_body_required(
    spec: dict[str, Any],
    operation: dict[str, Any],
) -> bool:
    request_body = _resolve_request_body(spec, operation)
    if request_body is None:
        return False
    return bool(request_body.get("required", False))


def _collect_request_content_types(
    spec: dict[str, Any],
    operation: dict[str, Any],
) -> tuple[str, ...]:
    request_body = _resolve_request_body(spec, operation)
    if request_body is None:
        return ()
    content = request_body.get("content")
    if not isinstance(content, dict):
        return ()
    return tuple(
        media_type
        for media_type in sorted(content)
        if isinstance(media_type, str)
    )


def _parameter_group_has_required(
    parameters: tuple[dict[str, Any], ...],
) -> bool:
    return any(
        bool(parameter.get("required", False)) for parameter in parameters
    )


def _collect_operation_parameters(
    parameters: tuple[dict[str, Any], ...],
) -> tuple[OperationParameter, ...]:
    return tuple(
        OperationParameter(
            name=str(parameter.get("name", "")).strip(),
            required=bool(parameter.get("required", False)),
        )
        for parameter in parameters
        if str(parameter.get("name", "")).strip()
    )


def _r_parameter_name(name: str) -> str:
    normalized = _normalize_identifier(name)
    if not normalized:
        return "param"
    if normalized[0].isdigit():
        return f"param_{normalized}"
    return normalized


def _r_operation_signature(prefix: str, operation: Operation) -> str:
    parts = ["client"]
    if operation.has_request_body:
        parts.append("body")
    if operation.has_path_params:
        parts.extend(
            _r_parameter_name(parameter.name)
            for parameter in operation.path_parameters
        )
    if operation.has_query_params:
        parts.extend(
            (
                _r_parameter_name(parameter.name)
                if parameter.required
                else f"{_r_parameter_name(parameter.name)} = NULL"
            )
            for parameter in operation.query_parameters
        )
    parts.append("headers = NULL")
    return f"{prefix}_{operation.operation_id}({', '.join(parts)})"


def _r_operation_manual_section(prefix: str, operation: Operation) -> list[str]:
    signature = _r_operation_signature(prefix, operation)
    description = (
        operation.summary.strip()
        if operation.summary is not None and operation.summary.strip()
        else f"Calls the {operation.method} {operation.path} endpoint."
    )
    lines = [
        f"\\section{{{prefix}_{operation.operation_id}}}{{",
        f"  \\code{{{signature}}}",
        "",
        f"  {description}",
        "",
        "  \\describe{",
        f"    \\item{{client}}{{Thin client created by \\code{{create_{prefix}_client()}}.}}",
    ]
    if operation.has_request_body:
        lines.append(
            "    \\item{body}{Request payload for this operation, "
            "encoded as JSON.}"
        )
    for parameter in operation.path_parameters:
        lines.extend(
            [
                f"    \\item{{{parameter.name}}}{{Path parameter "
                f"\\code{{{parameter.name}}}.}}",
            ]
        )
    for parameter in operation.query_parameters:
        qualifier = "Query" if parameter.required else "Optional query"
        lines.extend(
            [
                f"    \\item{{{parameter.name}}}{{{qualifier} parameter "
                f"\\code{{{parameter.name}}}.}}",
            ]
        )
    lines.extend(
        [
            "    \\item{headers}{Optional named list of per-request headers.}",
            "    \\item{Returns}{Parsed JSON response as a named list, or "
            "NULL when the response body is empty.}",
            "  }",
            "}",
            "",
        ]
    )
    return lines


def _collect_response_status_codes(operation: dict[str, Any]) -> set[int]:
    responses = operation.get("responses", {})
    if not isinstance(responses, dict):
        return set()
    status_codes: set[int] = set()
    for key in responses:
        try:
            status_codes.add(int(str(key)))
        except ValueError:
            continue
    return status_codes


def _assert_unique_operation_ids(
    *,
    spec_path: Path,
    operations: list[Operation],
) -> None:
    seen: dict[str, tuple[str, str]] = {}
    collisions: list[str] = []
    for operation in operations:
        existing = seen.get(operation.operation_id)
        if existing is None:
            seen[operation.operation_id] = (operation.method, operation.path)
            continue
        collisions.append(
            f"{operation.operation_id}: {existing[0]} {existing[1]} "
            f"and {operation.method} {operation.path}"
        )
    if collisions:
        joined = "; ".join(collisions)
        raise ValueError(
            f"Duplicate operationId values detected in {spec_path}: {joined}"
        )


def _render_typescript_openapi(spec_path: Path) -> str:
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "openapi.ts"
        if not OPENAPI_TYPESCRIPT_CLI.exists():
            raise RuntimeError(
                "openapi-typescript generation failed: missing repo-installed "
                "openapi-typescript CLI at "
                f"{OPENAPI_TYPESCRIPT_CLI}; run `npm ci` from repo root"
            )
        command = [
            str(OPENAPI_TYPESCRIPT_CLI),
            str(spec_path),
            "-o",
            str(output_path),
        ]
        try:
            result = subprocess.run(
                command,
                cwd=REPO_ROOT,
                check=False,
                text=True,
                capture_output=True,
                timeout=120,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "openapi-typescript generation failed: missing repo-installed "
                "CLI; run `npm ci` from repo root"
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
                "openapi-typescript generation timed out after 120s for "
                f"{spec_path} using command {' '.join(command)}: {details}"
            ) from exc
        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            details = stderr or stdout or "no output captured"
            raise RuntimeError(
                "openapi-typescript generation command failed for "
                f"{spec_path}: {details}"
            )
        return output_path.read_text(encoding="utf-8")


def _render_operations(operations: list[Operation]) -> str:
    lines = [
        (
            "// Code generated by scripts/release/generate_clients.py. "
            "DO NOT EDIT."
        ),
        "",
        "/** Describes one generated public operation entry in the static catalog. */",
        "export interface OperationDescriptor {",
        "  readonly operationId: string;",
        "  readonly method: string;",
        "  readonly path: string;",
        "  readonly summary?: string;",
        "}",
        "",
        "/** Catalog of generated public operations keyed by operationId. */",
        "export const operations = {",
    ]

    for operation in operations:
        summary_line = (
            f"    summary: {json.dumps(operation.summary)},"
            if operation.summary
            else None
        )
        lines.extend(
            [
                f"  {json.dumps(operation.operation_id)}: {{",
                f"    operationId: {json.dumps(operation.operation_id)},",
                f"    method: {json.dumps(operation.method)},",
                f"    path: {json.dumps(operation.path)},",
            ]
        )
        if summary_line is not None:
            lines.append(summary_line)
        lines.append("  },")

    lines.extend(
        [
            "} as const satisfies Record<string, OperationDescriptor>;",
            "",
            "/** Union of all generated public operation identifiers. */",
            "export type OperationId = keyof typeof operations;",
            "/** Static type representing the generated public operations catalog. */",
            "export type GeneratedOperationCatalog = typeof operations;",
            "",
        ]
    )
    return "\n".join(lines)


def _render_typescript_types(
    spec: dict[str, Any],
    operations: list[Operation],
) -> str:
    schema_names = _collect_public_schema_names(spec, operations)
    lines = [
        (
            "// Code generated by scripts/release/generate_clients.py. "
            "DO NOT EDIT."
        ),
        "",
        "import type {",
        "  components as GeneratedComponents,",
        "  operations as GeneratedOperations,",
        '} from "./generated/openapi.js";',
        "",
        "type EmptyObject = Record<string, never>;",
        "type SuccessStatus = 200 | 201 | 202 | 203 | 204 | 205 | 206 | 207 | 208 | 226;",
        "type Simplify<T> = { [K in keyof T]: T[K] } & {};",
        "type OperationOf<TId extends keyof GeneratedOperations> = GeneratedOperations[TId];",
        "type ParametersOf<T> = T extends { parameters: infer TParameters } ? TParameters : EmptyObject;",
        'type FieldOf<TParameters, TKey extends "query" | "header" | "path"> = TParameters extends { [K in TKey]?: infer TValue }',
        "  ? [TValue] extends [never]",
        "    ? EmptyObject",
        "    : TValue",
        "  : EmptyObject;",
        "type ContentOf<TContent, TMediaType extends string> = TContent extends Record<PropertyKey, unknown>",
        "  ? TMediaType extends keyof TContent",
        "    ? TContent[TMediaType]",
        "    : never",
        "  : never;",
        "type JsonContentOf<TContent> = TContent extends Record<PropertyKey, unknown>",
        '  ? "application/json" extends keyof TContent',
        '    ? TContent["application/json"]',
        "    : null",
        "  : null;",
        "type RequestContentTypesOf<T> = T extends { requestBody: { content: infer TContent } }",
        "  ? Extract<keyof TContent, string>",
        "  : never;",
        "type RequestBodyOf<T> = T extends { requestBody: { content: infer TContent } }",
        "  ? ContentOf<TContent, RequestContentTypesOf<T>>",
        "  : never;",
        "type RequestBodyForContentType<T, TContentType extends string> = T extends { requestBody: { content: infer TContent } }",
        "  ? ContentOf<TContent, TContentType>",
        "  : never;",
        "type ResponsesOf<T> = T extends { responses: infer TResponses } ? TResponses : EmptyObject;",
        "type StatusCodeOf<TResponses> = Extract<keyof TResponses, number>;",
        "type SuccessStatusCodeOf<TResponses> = Extract<StatusCodeOf<TResponses>, SuccessStatus>;",
        "type ErrorStatusCodeOf<TResponses> = Exclude<StatusCodeOf<TResponses>, SuccessStatus>;",
        "type ResponseBodyOf<TEntry> = TEntry extends { content: infer TContent }",
        "  ? JsonContentOf<TContent>",
        "  : null;",
        'type DefaultResponseDataOf<TResponses> = "default" extends keyof TResponses',
        '  ? ResponseBodyOf<TResponses["default"]>',
        "  : never;",
        "type ResponseDataOf<TResponses, TStatusCodes extends number> = TStatusCodes extends StatusCodeOf<TResponses>",
        "  ? ResponseBodyOf<TResponses[TStatusCodes]>",
        "  : never;",
        "type ErrorDataOf<TResponses> =",
        "  | ResponseDataOf<TResponses, ErrorStatusCodeOf<TResponses>>",
        "  | DefaultResponseDataOf<TResponses>;",
        "",
        "/** Named aliases for generated OpenAPI component schemas. */",
    ]

    for schema_name in schema_names:
        alias_name = _schema_alias_name(schema_name)
        lines.append(f"/** OpenAPI component schema `{schema_name}`. */")
        lines.append(
            f'export type {alias_name} = GeneratedComponents["schemas"][{json.dumps(schema_name)}];'
        )

    lines.extend(
        ["", "/** Operation-specific request and response helpers. */"]
    )

    for operation in operations:
        base_name = operation.type_base_name
        lines.extend(
            [
                "",
                f"type {base_name}Spec = OperationOf<{json.dumps(operation.operation_id)}>;",
                f"export type {base_name}Operation = {base_name}Spec;",
                f'export type {base_name}PathParams = Simplify<FieldOf<ParametersOf<{base_name}Spec>, "path">>;',
                f'export type {base_name}QueryParams = Simplify<FieldOf<ParametersOf<{base_name}Spec>, "query">>;',
                f'export type {base_name}Headers = Simplify<FieldOf<ParametersOf<{base_name}Spec>, "header">>;',
                f"export type {base_name}RequestContentType = RequestContentTypesOf<{base_name}Spec>;",
                f"export type {base_name}RequestBody = RequestBodyOf<{base_name}Spec>;",
                f"export type {base_name}RequestBodyForContentType<TContentType extends {base_name}RequestContentType> = RequestBodyForContentType<{base_name}Spec, TContentType>;",
                f"export type {base_name}Responses = ResponsesOf<{base_name}Spec>;",
                f"/** Union of success response payloads for `{operation.operation_id}`. */",
                f"export type {base_name}SuccessData = ResponseDataOf<{base_name}Responses, SuccessStatusCodeOf<{base_name}Responses>>;",
                f"/** Union of non-success response payloads for `{operation.operation_id}`. */",
                f"export type {base_name}ErrorData = ErrorDataOf<{base_name}Responses>;",
            ]
        )
        lines.extend(
            f"export type {base_name}Response{status_code} = "
            f"ResponseBodyOf<{base_name}Responses[{status_code}]>;"
            for status_code in operation.response_status_codes
        )
    lines.append("")
    return "\n".join(lines)


def _collect_public_schema_names(
    spec: dict[str, Any],
    operations: list[Operation],
) -> list[str]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return []

    reachable_schema_names: set[str] = set()
    visited_refs: set[str] = set()
    for operation in operations:
        path_item = paths.get(operation.path)
        if not isinstance(path_item, dict):
            continue
        raw_operation = path_item.get(operation.method.lower())
        if not isinstance(raw_operation, dict):
            continue
        _walk_for_public_schema_refs(
            spec,
            raw_operation,
            reachable_schema_names,
            visited_refs,
        )
        _walk_for_public_schema_refs(
            spec,
            path_item.get("parameters"),
            reachable_schema_names,
            visited_refs,
        )
        _walk_for_public_schema_refs(
            spec,
            raw_operation.get("parameters"),
            reachable_schema_names,
            visited_refs,
        )
    return sorted(reachable_schema_names)


def _walk_for_public_schema_refs(
    spec: dict[str, Any],
    node: Any,
    reachable_schema_names: set[str],
    visited_refs: set[str],
) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_for_public_schema_refs(
                spec,
                item,
                reachable_schema_names,
                visited_refs,
            )
        return

    if not isinstance(node, dict):
        return

    ref = node.get("$ref")
    if isinstance(ref, str):
        if ref in visited_refs:
            return
        visited_refs.add(ref)
        if ref.startswith("#/components/schemas/"):
            reachable_schema_names.add(ref.rsplit("/", 1)[-1])
        resolved = _resolve_local_ref(spec, ref)
        _walk_for_public_schema_refs(
            spec,
            resolved,
            reachable_schema_names,
            visited_refs,
        )
        return

    for value in node.values():
        _walk_for_public_schema_refs(
            spec,
            value,
            reachable_schema_names,
            visited_refs,
        )


def _resolve_local_ref(spec: dict[str, Any], ref: str) -> Any:
    if not ref.startswith("#/"):
        raise ValueError(f"Unsupported OpenAPI reference: {ref!r}")

    current: Any = spec
    for segment in ref[2:].split("/"):
        if not isinstance(current, dict) or segment not in current:
            raise ValueError(f"Missing referenced OpenAPI node: {ref}")
        current = current[segment]
    return current


def _schema_alias_name(schema_name: str) -> str:
    if _VALID_IDENTIFIER.fullmatch(schema_name):
        return schema_name
    normalized = re.sub(r"[^A-Za-z0-9_$]+", "_", schema_name).strip("_")
    if not normalized:
        normalized = "GeneratedSchema"
    if normalized[0].isdigit():
        normalized = f"Schema_{normalized}"
    return normalized


def _r_operation_function_name(prefix: str, operation_id: str) -> str:
    """Return the exported R function name for one operation."""
    return f"{prefix}_{operation_id}"


def _r_exported_function_names(
    prefix: str, operations: list[Operation]
) -> tuple[str, ...]:
    """Return the exported R function names for a client prefix."""
    exports = [
        f"create_{prefix}_client",
        f"{prefix}_bearer_token",
    ]
    exports.extend(
        _r_operation_function_name(prefix, operation.operation_id)
        for operation in operations
    )
    return tuple(exports)


def _r_package_doc_filename(target: GenerationTarget) -> str:
    """Return the Rd filename for the generated R package docs."""
    return f"{target.r_package_name}.Rd"


def _render_r_license_text(target: GenerationTarget) -> str:
    """Render the internal R package license notice text."""
    return "\n".join(
        [
            f"{target.r_package_title}",
            "",
            "Copyright (c) 2026 3M Cloud. All rights reserved.",
            "",
            "This package is generated for internal Nova use only.",
            "All rights reserved.",
            "",
        ]
    )


def _render_r(operations: list[Operation], catalog_function_name: str) -> str:
    prefix = catalog_function_name.removesuffix("_operation_catalog")
    lines = [
        "# Code generated by scripts/release/generate_clients.py. DO NOT EDIT.",
        "",
    ]

    for operation in operations:
        function_name = _r_operation_function_name(
            prefix, operation.operation_id
        )
        signature_parts = ["client"]
        call_parts = [
            "    client = client,",
            f'    operation_id = "{operation.operation_id}",',
            f'    method = "{operation.method}",',
            f'    path = "{operation.path}",',
        ]
        if operation.has_request_body:
            signature_parts.append(
                "body" if operation.has_required_request_body else "body = NULL"
            )
            call_parts.append("    body = body,")
        if operation.has_path_params:
            path_args = [
                _r_parameter_name(parameter.name)
                for parameter in operation.path_parameters
            ]
            signature_parts.extend(path_args)
            path_params = ", ".join(
                f"{parameter.name} = {_r_parameter_name(parameter.name)}"
                for parameter in operation.path_parameters
            )
            call_parts.append(f"    path_params = list({path_params}),")
        if operation.has_query_params:
            signature_parts.extend(
                (
                    _r_parameter_name(parameter.name)
                    if parameter.required
                    else f"{_r_parameter_name(parameter.name)} = NULL"
                )
                for parameter in operation.query_parameters
            )
            query_params = ", ".join(
                f"{parameter.name} = {_r_parameter_name(parameter.name)}"
                for parameter in operation.query_parameters
            )
            call_parts.append(f"    query = list({query_params}),")
        signature_parts.append("headers = NULL")
        call_parts.append("    headers = headers,")
        call_parts.extend(
            [
                f"    requires_body = {'TRUE' if operation.has_required_request_body else 'FALSE'},",
                f"    accepts_body = {'TRUE' if operation.has_request_body else 'FALSE'}",
            ]
        )
        lines.extend(
            [
                f"{function_name} <- function(",
                "  " + ",\n  ".join(signature_parts),
                ") {",
                f"  {prefix}_api_call(",
                *call_parts,
                "  )",
                "}",
                "",
            ]
        )
    return "\n".join(lines)


def _render_r_client(target: GenerationTarget) -> str:
    prefix = target.r_client_prefix
    client_constructor = f"create_{prefix}_client"
    error_class_name = f"{prefix}_api_error"
    lines = [
        "# Code generated by scripts/release/generate_clients.py. DO NOT EDIT.",
        "",
        f"{prefix}_null_coalesce <- function(value, fallback) {{",
        "  if (is.null(value)) {",
        "    fallback",
        "  } else {",
        "    value",
        "  }",
        "}",
        "",
        f"{prefix}_normalize_named_list <- function(value, label) {{",
        "  if (is.null(value)) {",
        "    return(list())",
        "  }",
        "  if (is.atomic(value) && !is.list(value)) {",
        "    value <- as.list(value)",
        "  }",
        "  if (!is.list(value)) {",
        '    stop(sprintf("%s must be a named list", label), call. = FALSE)',
        "  }",
        "  item_names <- names(value)",
        "  if (is.null(item_names)) {",
        '    stop(sprintf("%s must be a named list", label), call. = FALSE)',
        "  }",
        "  cleaned <- list()",
        "  for (index in seq_along(value)) {",
        "    item_name <- item_names[[index]]",
        "    if (is.na(item_name) || !nzchar(item_name)) {",
        '      stop(sprintf("%s names must be non-empty", label), call. = FALSE)',
        "    }",
        "    item_value <- value[[index]]",
        "    if (is.null(item_value)) {",
        "      next",
        "    }",
        "    cleaned[[item_name]] <- item_value",
        "  }",
        "  cleaned",
        "}",
        "",
        f"{prefix}_prune_null_headers <- function(value) {{",
        "  if (length(value) == 0L) {",
        "    return(value)",
        "  }",
        "  value[!vapply(value, is.null, logical(1))]",
        "}",
        "",
        f"{prefix}_normalize_base_url <- function(base_url) {{",
        "  if (!is.character(base_url) || length(base_url) != 1L || !nzchar(base_url)) {",
        '    stop("base_url must be a non-empty string", call. = FALSE)',
        "  }",
        '  sub("/+$", "", base_url)',
        "}",
        "",
        f"{prefix}_resolve_path <- function(path, path_params) {{",
        f'  path_params <- {prefix}_normalize_named_list(path_params, "path_params")',
        "  resolved_path <- path",
        "  if (length(path_params) > 0L) {",
        "    for (param_name in names(path_params)) {",
        "      resolved_path <- gsub(",
        '        sprintf("{%s}", param_name),',
        "        utils::URLencode(as.character(path_params[[param_name]]), reserved = TRUE),",
        "        resolved_path,",
        "        fixed = TRUE",
        "      )",
        "    }",
        "  }",
        "  missing_path_params <- regmatches(",
        '    resolved_path, gregexpr("\\\\{[^}]+\\\\}", resolved_path, perl = TRUE)',
        "  )[[1]]",
        "  if (length(missing_path_params) > 0L) {",
        '    stop(sprintf("missing path parameter(s): %s", paste(missing_path_params, collapse = ", ")), call. = FALSE)',
        "  }",
        "  resolved_path",
        "}",
        "",
        f"{prefix}_parse_json_response <- function(response) {{",
        "  if (length(httr2::resp_body_raw(response)) == 0L) {",
        "    return(NULL)",
        "  }",
        "  httr2::resp_body_json(response, simplifyVector = FALSE, check_type = FALSE)",
        "}",
        "",
        f"{prefix}_parse_success_response <- function(response) {{",
        f"  {prefix}_parse_json_response(response)",
        "}",
        "",
        f"{prefix}_response_body_text <- function(response) {{",
        "  if (length(httr2::resp_body_raw(response)) == 0L) {",
        '    return("")',
        "  }",
        "  httr2::resp_body_string(response)",
        "}",
        "",
        f"{prefix}_default_user_agent <- function() {{",
        f'  sprintf("{target.r_package_name}/%s", utils::packageVersion("{target.r_package_name}"))',
        "}",
        "",
        f"{prefix}_bearer_token <- function(token = NULL, env_var = {json.dumps(prefix.upper() + '_BEARER_TOKEN')}) {{",
        "  if (!is.null(token)) {",
        "    token_chr <- as.character(token)",
        "    if (length(token_chr) == 0L) {",
        "      return(NULL)",
        "    }",
        "    token_value <- token_chr[[1L]]",
        "    if (is.na(token_value) || !nzchar(token_value)) {",
        "      return(NULL)",
        "    }",
        "    return(token_value)",
        "  }",
        "  env_var_chr <- as.character(env_var)",
        "  if (length(env_var_chr) == 0L) {",
        "    return(NULL)",
        "  }",
        "  env_var_value <- env_var_chr[[1L]]",
        "  if (is.na(env_var_value) || !nzchar(env_var_value)) {",
        "    return(NULL)",
        "  }",
        "  env_value <- Sys.getenv(env_var_value, unset = '')",
        "  if (!nzchar(env_value)) {",
        "    return(NULL)",
        "  }",
        "  env_value",
        "}",
        "",
        f"{prefix}_normalize_user_agent <- function(user_agent = NULL) {{",
        "  if (is.null(user_agent)) {",
        "    return(NULL)",
        "  }",
        "  user_agent_chr <- as.character(user_agent)",
        "  if (length(user_agent_chr) == 0L) {",
        "    return(NULL)",
        "  }",
        "  user_agent_value <- user_agent_chr[[1L]]",
        "  if (is.na(user_agent_value) || !nzchar(user_agent_value)) {",
        "    return(NULL)",
        "  }",
        "  user_agent_value",
        "}",
        "",
        f"{prefix}_decode_error_envelope <- function(response, status = NULL) {{",
        "  parsed_body <- tryCatch(",
        f"    {prefix}_parse_json_response(response),",
        "    error = function(...) NULL",
        "  )",
        "  if (!is.list(parsed_body) || is.null(parsed_body$error) || !is.list(parsed_body$error)) {",
        "    fallback_status <- if (is.null(status)) 'unknown' else as.character(status)",
        f"    fallback_message <- if (!nzchar({prefix}_response_body_text(response))) {{",
        '      sprintf("HTTP %s response", fallback_status)',
        "    } else {",
        f"      {prefix}_response_body_text(response)",
        "    }",
        "    return(",
        "      list(",
        '        code = paste0("http_", fallback_status),',
        "        message = fallback_message,",
        "        details = list(),",
        "        request_id = NULL",
        "      )",
        "    )",
        "  }",
        "  error_body <- parsed_body$error",
        "  request_id <- error_body$request_id",
        "  if (length(request_id) == 0L) {",
        "    request_id <- NULL",
        "  }",
        "  list(",
        "    code = as.character(error_body$code),",
        "    message = as.character(error_body$message),",
        f"    details = {prefix}_null_coalesce(error_body$details, list()),",
        "    request_id = request_id",
        "  )",
        "}",
        "",
        f"{prefix}_error_body <- function(response) {{",
        f"  error <- {prefix}_decode_error_envelope(response, status = httr2::resp_status(response))",
        '  sprintf("[%s] %s", error$code, error$message)',
        "}",
        "",
        f"{prefix}_error_condition <- function(error, status, operation_id, method, path, response = NULL, parent = NULL) {{",
        "  structure(",
        "    list(",
        "      message = error$message,",
        "      call = NULL,",
        "      code = error$code,",
        "      status = status,",
        "      request_id = error$request_id,",
        "      details = error$details,",
        "      operation_id = operation_id,",
        "      method = method,",
        "      path = path,",
        "      resp = response,",
        "      parent = parent",
        "    ),",
        f'    class = c("{error_class_name}", parent, "error", "condition")',
        "  )",
        "}",
        "",
        f"conditionMessage.{error_class_name} <- function(c) {{",
        '  sprintf("[%s] %s", c$code, c$message)',
        "}",
        "",
        f"{prefix}_apply_request <- function(http_request, request_headers, bearer_token, user_agent) {{",
        "  if (length(request_headers) > 0L) {",
        "    http_request <- do.call(httr2::req_headers, c(list(http_request), request_headers))",
        "  }",
        "  if (!is.null(user_agent) && nzchar(user_agent)) {",
        "    http_request <- httr2::req_user_agent(http_request, user_agent)",
        "  }",
        '  has_authorization <- any(tolower(names(request_headers)) == "authorization")',
        "  if (!is.null(bearer_token) && nzchar(bearer_token) && !has_authorization) {",
        "    http_request <- httr2::req_auth_bearer_token(http_request, bearer_token)",
        "  }",
        "  http_request",
        "}",
        "",
        f"{prefix}_api_call <- function(",
        "  client,",
        "  operation_id,",
        "  method,",
        "  path,",
        "  body = NULL,",
        "  path_params = NULL,",
        "  query = NULL,",
        "  headers = NULL,",
        "  requires_body = FALSE,",
        "  accepts_body = FALSE",
        ") {",
        f'  if (!inherits(client, "{prefix}_client")) {{',
        f'    stop("client must be created by create_{prefix}_client()", call. = FALSE)',
        "  }",
        f'  query <- {prefix}_normalize_named_list(query, "query")',
        f'  request_headers <- {prefix}_normalize_named_list(headers, "headers")',
        "  merged_headers <- c(client$default_headers, request_headers)",
        "  if (length(merged_headers) > 0L) {",
        "    merged_headers <- merged_headers[!duplicated(tolower(names(merged_headers)), fromLast = TRUE)]",
        "  }",
        f"  merged_headers <- {prefix}_prune_null_headers(merged_headers)",
        f"  resolved_path <- {prefix}_resolve_path(path, path_params)",
        "  if (is.null(body) && isTRUE(requires_body)) {",
        '    stop(sprintf("operation %s requires a request body", operation_id), call. = FALSE)',
        "  }",
        "  if (!is.null(body) && !isTRUE(accepts_body)) {",
        '    stop(sprintf("operation %s does not accept a request body", operation_id), call. = FALSE)',
        "  }",
        "  http_request <- httr2::request(paste0(client$base_url, resolved_path))",
        "  http_request <- httr2::req_method(http_request, method)",
        "  if (length(query) > 0L) {",
        "    http_request <- do.call(httr2::req_url_query, c(list(http_request), query))",
        "  }",
        f"  http_request <- {prefix}_apply_request(http_request, merged_headers, client$bearer_token, client$user_agent)",
        "  http_request <- httr2::req_options(http_request, timeout = client$timeout_seconds)",
        "  if (!is.null(body)) {",
        '    http_request <- httr2::req_body_json(http_request, body, auto_unbox = TRUE, null = "null")',
        "  }",
        "  http_request <- httr2::req_error(http_request, body = function(resp) {",
        f"    {prefix}_error_body(resp)",
        "  })",
        "  tryCatch(",
        "    {",
        "      response <- httr2::req_perform(http_request)",
        f"      {prefix}_parse_success_response(response)",
        "    },",
        "    httr2_http = function(cnd) {",
        f"      error <- {prefix}_decode_error_envelope(cnd$resp, status = cnd$status)",
        "      stop(",
        f"        {prefix}_error_condition(",
        "          error = error,",
        "          status = cnd$status,",
        "          operation_id = operation_id,",
        "          method = method,",
        "          path = resolved_path,",
        "          response = cnd$resp,",
        "          parent = class(cnd)",
        "        )",
        "      )",
        "    }",
        "  )",
        "}",
        "",
        f"{client_constructor} <- function(",
        "  base_url,",
        "  bearer_token = NULL,",
        f"  bearer_token_env = {json.dumps(prefix.upper() + '_BEARER_TOKEN')},",
        "  default_headers = NULL,",
        "  timeout_seconds = 30,",
        "  user_agent = NULL",
        ") {",
        f"  base_url <- {prefix}_normalize_base_url(base_url)",
        "  if (!is.numeric(timeout_seconds) || length(timeout_seconds) != 1L || is.na(timeout_seconds) || !is.finite(timeout_seconds) || timeout_seconds <= 0) {",
        '    stop("timeout_seconds must be a finite positive number", call. = FALSE)',
        "  }",
        f'  default_headers <- {prefix}_normalize_named_list(default_headers, "default_headers")',
        "  client <- list(",
        "    base_url = base_url,",
        f"    bearer_token = {prefix}_bearer_token(token = bearer_token, env_var = bearer_token_env),",
        "    default_headers = default_headers,",
        "    timeout_seconds = timeout_seconds,",
        f"    user_agent = {prefix}_null_coalesce({prefix}_normalize_user_agent(user_agent), {prefix}_default_user_agent())",
        "  )",
        f'  class(client) <- c("{prefix}_client", "list")',
        "  client",
        "}",
        "",
    ]
    return "\n".join(lines)


def _render_r_description(target: GenerationTarget) -> str:
    package_root = target.r_output_path.parent.parent
    version = _resolve_r_package_version(package_root)
    lines = [
        f"Package: {target.r_package_name}",
        "Type: Package",
        f"Title: {target.r_package_title}",
        f"Version: {version}",
        f"Authors@R: {_R_PACKAGE_MAINTAINER}",
        f"Description: {target.r_package_description}",
        "License: file LICENSE",
        "Encoding: UTF-8",
        "Roxygen: list(markdown = TRUE)",
        "RoxygenNote: 7.3.3",
        "Imports:",
        "    httr2",
        "Suggests:",
        "    testthat (>= 3.2.3),",
        "    withr (>= 3.0.2)",
        "Config/testthat/edition: 3",
        "",
    ]
    return "\n".join(lines)


def _resolve_r_package_version(package_root: Path) -> str:
    description_path = package_root / "DESCRIPTION"
    if not description_path.exists():
        return _DEFAULT_R_PACKAGE_VERSION

    version_pattern = re.compile(r"(?m)^Version:\s*([^\n]+)\s*$")
    match = version_pattern.search(description_path.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(
            f"DESCRIPTION version field not found: {description_path}"
        )

    version = match.group(1).strip()
    if not version:
        raise ValueError(
            f"DESCRIPTION version field must be non-empty: {description_path}"
        )
    return version


def _render_r_namespace(target: GenerationTarget) -> str:
    _, operations = _load_operations(target.spec_path)
    exports = _r_exported_function_names(target.r_client_prefix, operations)
    error_class_name = f"{target.r_client_prefix}_api_error"
    lines = [
        "# Generated by roxygen2: do not edit by hand",
        "",
        f"S3method(conditionMessage,{error_class_name})",
        "",
    ]
    lines.extend(f"export({name})" for name in exports)
    lines.append("")
    return "\n".join(lines)


def _render_r_readme(target: GenerationTarget) -> str:
    client_prefix = target.r_client_prefix
    short_prefix = client_prefix.removeprefix("nova_")
    # TARGETS currently contains only the nova_file R package, so the README
    # example stays keyed to target metadata rather than per-operation logic.
    constructor = f"create_{client_prefix}_client"
    operation_prefix = f"nova_{short_prefix}"
    lines = [
        f"# `{target.r_package_name}`",
        "",
        f"Generated R client for the Nova {short_prefix} API.",
        "",
        "This package is generated from committed OpenAPI and is kept in-repo so",
        "Nova release tooling can build and check the real package tree.",
        "The generated client is intentionally thin and follows the current",
        "public Nova file API contract: bearer JWT auth, JSON bodies,",
        "concrete path/query parameters, and plain R list responses.",
        "",
        "## Surface",
        "",
        f"- `{constructor}`",
        f"- `{target.r_client_prefix}_bearer_token`",
        f"- endpoint wrappers named `{target.r_client_prefix}_<operation_id>`",
        "",
        "## Example",
        "",
        "```r",
    ]
    lines.extend(
        [
            f"client <- {constructor}(",
            '  "https://nova.example/",',
            '  bearer_token = "eyJhbGciOi...",',
            ")",
            "",
            f"result <- {operation_prefix}_create_export(",
            "  client,",
            "  body = list(",
            '    source_key = "uploads/scope-1/source.csv",',
            '    filename = "source.csv"',
            "  ),",
            '  headers = list("Idempotency-Key" = "req-123")',
            ")",
            "result$export_id",
            "result$status",
            "",
            f"exports <- {operation_prefix}_list_exports(client, limit = 25)",
            f"export <- {operation_prefix}_get_export(client, export_id = result$export_id)",
        ]
    )
    lines.extend(["```", ""])
    return "\n".join(lines)


def _render_r_package_manual(target: GenerationTarget) -> str:
    _, operations = _load_operations(target.spec_path)
    exports = _r_exported_function_names(target.r_client_prefix, operations)
    constructor = f"create_{target.r_client_prefix}_client"
    bearer_helper = f"{target.r_client_prefix}_bearer_token"
    bearer_env_var = f"{target.r_client_prefix.upper()}_BEARER_TOKEN"
    package_name = target.r_package_name
    lines = [
        f"\\name{{{package_name}}}",
        "",
    ]
    lines.extend(f"\\alias{{{name}}}" for name in (package_name, *exports))
    lines.extend(
        [
            "\\docType{package}",
            f"\\title{{{target.r_package_title}}}",
            f"\\description{{{target.r_package_description}}}",
            "\\usage{",
            f'  {constructor}(base_url, bearer_token = NULL, bearer_token_env = "{bearer_env_var}", default_headers = NULL, timeout_seconds = 30, user_agent = NULL)',
            f'  {bearer_helper}(token = NULL, env_var = "{bearer_env_var}")',
            "}",
            "",
            "\\arguments{",
            "  \\item{base_url}{Base URL for the Nova API, without a trailing slash requirement.}",
            "  \\item{bearer_token}{Explicit bearer token used for Authorization headers when request headers do not already provide one.}",
            "  \\item{bearer_token_env}{Environment variable name used as an optional bearer-token fallback.}",
            "  \\item{default_headers}{Named list of default request headers applied to every request.}",
            "  \\item{timeout_seconds}{Positive request timeout in seconds.}",
            "  \\item{user_agent}{Optional explicit user agent string.}",
            "  \\item{token}{Explicit bearer token string.}",
            "  \\item{env_var}{Environment variable name used to resolve a bearer token.}",
            "}",
            "",
            "\\value{",
            "  The constructor returns a thin client configuration object.",
            "  The bearer-token helper returns an explicit or environment-derived token, or NULL when none is available.",
            "}",
            "",
        ]
    )
    for operation in operations:
        lines.extend(
            _r_operation_manual_section(target.r_client_prefix, operation)
        )
    lines.extend(
        [
            "\\keyword{package}",
            "",
        ]
    )
    return "\n".join(lines)


def _render_r_tests_entrypoint(target: GenerationTarget) -> str:
    lines = [
        "library(testthat)",
        f'library("{target.r_package_name}", character.only = TRUE)',
        f'test_check("{target.r_package_name}")',
        "",
    ]
    return "\n".join(lines)


def _render_r_tests(target: GenerationTarget) -> str:
    client_prefix = target.r_client_prefix
    short_prefix = client_prefix.removeprefix("nova_")
    constructor = f"create_{client_prefix}_client"
    default_user_agent = f"{client_prefix}_default_user_agent()"
    bearer_env_var = f"NOVA_{short_prefix.upper()}_BEARER_TOKEN"
    namespace = f"nova.sdk.r.{short_prefix}"
    operation_prefix = f"nova_{short_prefix}"
    api_error_class = f"{client_prefix}_api_error"
    lines = [
        'test_that("constructor resolves explicit and environment bearer tokens", {',
        f'  withr::local_envvar({bearer_env_var} = "env-token-123")',
        f'  env_client <- {constructor}("https://nova.example/")',
        '  expect_equal(env_client$bearer_token, "env-token-123")',
        f'  explicit_client <- {constructor}("https://nova.example/", bearer_token = "explicit-token-123")',
        '  expect_equal(explicit_client$bearer_token, "explicit-token-123")',
        "})",
        "",
        'test_that("constructor treats zero-length bearer tokens as absent", {',
        f"  withr::local_envvar({bearer_env_var} = NA_character_)",
        f'  client <- {constructor}("https://nova.example/", bearer_token = character(0))',
        "  expect_null(client$bearer_token)",
        "})",
        "",
        'test_that("constructor normalizes invalid user agents to the default", {',
        f'  client <- {constructor}("https://nova.example/", user_agent = character(0))',
        f"  expect_equal(client$user_agent, {default_user_agent})",
        f'  client_na <- {constructor}("https://nova.example/", user_agent = NA_character_)',
        f"  expect_equal(client_na$user_agent, {default_user_agent})",
        "})",
        "",
        'test_that("generated package exports thin endpoint wrappers", {',
        f'  exports <- getNamespaceExports("{namespace}")',
        f'  expect_true("{operation_prefix}_create_export" %in% exports)',
        f'  expect_true("{operation_prefix}_get_export" %in% exports)',
        f'  expect_true("{operation_prefix}_list_exports" %in% exports)',
        f'  expect_false("{operation_prefix}_request_descriptor" %in% exports)',
        f'  expect_false("{operation_prefix}_execute_operation" %in% exports)',
        "})",
        "",
        'test_that("request construction uses concrete params and bearer auth", {',
        "  observed_request <- NULL",
        "  mocked_response <- httr2::response(",
        "    status_code = 200,",
        '    url = "https://nova.example/v1/exports/export-123",',
        '    headers = list(`content-type` = "application/json"),',
        '    body = charToRaw(\'{"export_id":"export-123","source_key":"uploads/scope-1/source.csv","filename":"source.csv","status":"queued","output":null,"error":null,"created_at":"2026-03-25T00:00:00Z","updated_at":"2026-03-25T00:00:00Z"}\')',
        "  )",
        f"  withr::local_envvar({bearer_env_var} = NA_character_)",
        "  result <- httr2::with_mocked_responses(",
        "    function(req) {",
        "      observed_request <<- req",
        "      mocked_response",
        "    },",
        "    {",
        f'      client <- {constructor}("https://nova.example/", bearer_token = "token-123", timeout_seconds = 12)',
        f'      {operation_prefix}_get_export(client, export_id = "export-123", headers = list(`X-Request-Id` = "req-123"))',
        "    }",
        "  )",
        '  expect_equal(result$export_id, "export-123")',
        '  expect_equal(result$status, "queued")',
        '  expect_equal(observed_request$url, "https://nova.example/v1/exports/export-123")',
        '  expect_equal(observed_request$method, "GET")',
        '  expect_true("Authorization" %in% names(observed_request$headers))',
        '  expect_equal(observed_request$headers$`X-Request-Id`, "req-123")',
        "  expect_equal(observed_request$options$timeout, 12)",
        "})",
        "",
        'test_that("lowercase authorization headers suppress bearer injection", {',
        "  observed_request <- NULL",
        "  mocked_response <- httr2::response(",
        "    status_code = 200,",
        '    url = "https://nova.example/v1/exports/export-123",',
        '    headers = list(`content-type` = "application/json"),',
        '    body = charToRaw(\'{"export_id":"export-123","source_key":"uploads/scope-1/source.csv","filename":"source.csv","status":"queued","output":null,"error":null,"created_at":"2026-03-25T00:00:00Z","updated_at":"2026-03-25T00:00:00Z"}\')',
        "  )",
        "  result <- httr2::with_mocked_responses(",
        "    function(req) {",
        "      observed_request <<- req",
        "      mocked_response",
        "    },",
        "    {",
        f'      client <- {constructor}("https://nova.example/", bearer_token = "token-123")',
        f'      {operation_prefix}_get_export(client, export_id = "export-123", headers = list(authorization = "Bearer custom"))',
        "    }",
        "  )",
        '  auth_positions <- which(tolower(names(observed_request$headers)) == "authorization")',
        "  expect_length(auth_positions, 1L)",
        '  expect_identical(names(observed_request$headers)[auth_positions[[1L]]], "authorization")',
        '  expect_equal(result$export_id, "export-123")',
        "})",
        "",
        'test_that("request construction encodes query params and JSON bodies", {',
        "  observed_requests <- list()",
        "  mocked_response <- httr2::response(",
        "    status_code = 200,",
        '    url = "https://nova.example/v1/exports",',
        '    headers = list(`content-type` = "application/json"),',
        "    body = charToRaw('{\"exports\":[]}')",
        "  )",
        "  httr2::with_mocked_responses(",
        "    function(req) {",
        "      observed_requests[[length(observed_requests) + 1L]] <<- req",
        "      mocked_response",
        "    },",
        "    {",
        f'      client <- {constructor}("https://nova.example/", bearer_token = "token-123")',
        f"      {operation_prefix}_list_exports(client, limit = 25)",
        f"      {operation_prefix}_create_export(",
        "        client,",
        "        body = list(",
        '          source_key = "uploads/scope-1/source.csv",',
        '          filename = "source.csv"',
        "        ),",
        '        headers = list("Idempotency-Key" = "req-123")',
        "      )",
        "    }",
        "  )",
        "  expect_length(observed_requests, 2L)",
        '  expect_equal(observed_requests[[1]]$method, "GET")',
        '  expect_equal(observed_requests[[1]]$url, "https://nova.example/v1/exports?limit=25")',
        '  expect_equal(observed_requests[[2]]$method, "POST")',
        '  expect_equal(observed_requests[[2]]$url, "https://nova.example/v1/exports")',
        '  expect_equal(observed_requests[[2]]$headers$`Idempotency-Key`, "req-123")',
        '  expect_equal(observed_requests[[2]]$body$content_type, "application/json")',
        '  expect_equal(observed_requests[[2]]$body$data$source_key, "uploads/scope-1/source.csv")',
        '  expect_equal(observed_requests[[2]]$body$data$filename, "source.csv")',
        "})",
        "",
        'test_that("structured errors preserve Nova error envelope fields", {',
        "  mocked_response <- httr2::response(",
        "    status_code = 503,",
        '    url = "https://nova.example/v1/exports",',
        '    headers = list(`content-type` = "application/json"),',
        '    body = charToRaw(\'{"error":{"code":"queue_unavailable","message":"export creation failed because queue publish failed","request_id":"req-exports-503","details":{"backend":"sqs"}}}\')',
        "  )",
        "  error <- tryCatch(",
        "    httr2::with_mocked_responses(",
        "      function(req) mocked_response,",
        "      {",
        f'        client <- {constructor}("https://nova.example/", bearer_token = "token-123")',
        f'        {operation_prefix}_create_export(client, body = list(source_key = "uploads/scope-1/source.csv", filename = "source.csv"))',
        "      }",
        "    ),",
        f"    {api_error_class} = function(error) error",
        "  )",
        f'  expect_s3_class(error, "{api_error_class}")',
        '  expect_true(inherits(error, "httr2_http"))',
        '  expect_equal(error$code, "queue_unavailable")',
        "  expect_equal(error$status, 503L)",
        '  expect_equal(error$request_id, "req-exports-503")',
        '  expect_equal(error$details$backend, "sqs")',
        "  expect_equal(httr2::resp_status(error$resp), 503L)",
        '  expect_equal(conditionMessage(error), "[queue_unavailable] export creation failed because queue publish failed")',
        "})",
        "",
        'test_that("structured errors fall back to raw body text for non-JSON responses", {',
        "  mocked_response <- httr2::response(",
        "    status_code = 503,",
        '    url = "https://nova.example/v1/exports",',
        '    headers = list(`content-type` = "text/plain"),',
        '    body = charToRaw("service unavailable")',
        "  )",
        "  error <- tryCatch(",
        "    httr2::with_mocked_responses(",
        "      function(req) mocked_response,",
        "      {",
        f'        client <- {constructor}("https://nova.example/", bearer_token = "token-123")',
        f'        {operation_prefix}_create_export(client, body = list(source_key = "uploads/scope-1/source.csv", filename = "source.csv"))',
        "      }",
        "    ),",
        f"    {api_error_class} = function(error) error",
        "  )",
        f'  expect_s3_class(error, "{api_error_class}")',
        '  expect_true(inherits(error, "httr2_http"))',
        '  expect_equal(error$code, "http_503")',
        '  expect_match(conditionMessage(error), "service unavailable", fixed = TRUE)',
        "  expect_equal(httr2::resp_status(error$resp), 503L)",
        "})",
        "",
    ]
    return "\n".join(lines)


def _r_expected_package_files(target: GenerationTarget) -> tuple[Path, ...]:
    package_root = target.r_output_path.parent.parent
    return (
        package_root / "DESCRIPTION",
        package_root / "LICENSE",
        package_root / "NAMESPACE",
        package_root / "README.md",
        package_root / "R" / "client.R",
        package_root / "R" / "generated.R",
        package_root / "man" / _r_package_doc_filename(target),
        package_root / "tests" / "testthat.R",
        package_root / "tests" / "testthat" / "test-client.R",
    )


def _validate_r_package_tree(
    target: GenerationTarget,
    *,
    check: bool,
) -> list[str]:
    package_root = target.r_output_path.parent.parent
    expected_files = {
        path.relative_to(package_root).as_posix()
        for path in _r_expected_package_files(target)
    }

    if not check:
        package_root.mkdir(parents=True, exist_ok=True)
        return []

    if not package_root.exists():
        return [f"missing generated R package directory: {package_root}"]

    actual_files = {
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*")
        if path.is_file()
    }
    missing = sorted(expected_files - actual_files)
    extra = sorted(actual_files - expected_files)
    issues: list[str] = []
    if missing:
        issues.append(
            "missing expected generated R package artifacts in "
            f"{package_root}: {', '.join(missing)}"
        )
    if extra:
        issues.append(
            "unexpected generated R package artifacts in "
            f"{package_root}: {', '.join(extra)}"
        )
    return issues


def _write_or_check(path: Path, content: str, *, check: bool) -> list[str]:
    issues: list[str] = []
    if check:
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            issues.append(f"stale generated client artifact: {path}")
        return issues

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return issues


def _validate_generated_directory(
    package_root: Path, *, check: bool
) -> list[str]:
    generated_dir = package_root / "src" / "generated"
    expected_files = {"openapi.ts"}

    if not check:
        if generated_dir.exists():
            shutil.rmtree(generated_dir)
        generated_dir.mkdir(parents=True, exist_ok=True)
        return []

    if not generated_dir.exists():
        return [f"missing generated SDK directory: {generated_dir}"]

    current_file_names = {
        item.name for item in generated_dir.iterdir() if item.is_file()
    }
    missing = sorted(expected_files - current_file_names)
    extra = sorted(current_file_names - expected_files)
    issues: list[str] = []
    if missing:
        issues.append(
            "missing expected generated SDK artifacts in "
            f"{generated_dir}: {', '.join(missing)}"
        )
    if extra:
        issues.append(
            "unexpected generated SDK artifacts in "
            f"{generated_dir}: {', '.join(extra)}"
        )
    return issues


def _remove_stale_generated_directory(
    package_root: Path, *, check: bool
) -> list[str]:
    """Backward-compatible alias for legacy test/import paths."""
    return _validate_generated_directory(package_root, check=check)


def _generate_target(target: GenerationTarget, *, check: bool) -> list[str]:
    spec, operations = _load_operations(target.spec_path)
    issues: list[str] = []
    issues.extend(
        _validate_generated_directory(
            target.ts_package_root,
            check=check,
        )
    )
    issues.extend(
        _write_or_check(
            target.ts_package_root / "src" / "generated" / "openapi.ts",
            _render_typescript_openapi(target.spec_path),
            check=check,
        )
    )
    issues.extend(
        _write_or_check(
            target.ts_package_root / "src" / "operations.ts",
            _render_operations(operations),
            check=check,
        )
    )
    issues.extend(
        _write_or_check(
            target.ts_package_root / "src" / "types.ts",
            _render_typescript_types(spec, operations),
            check=check,
        )
    )
    issues.extend(_validate_r_package_tree(target, check=check))
    issues.extend(
        _write_or_check(
            target.r_output_path.parent.parent / "DESCRIPTION",
            _render_r_description(target),
            check=check,
        )
    )
    issues.extend(
        _write_or_check(
            target.r_output_path.parent.parent / "LICENSE",
            _render_r_license_text(target),
            check=check,
        )
    )
    issues.extend(
        _write_or_check(
            target.r_output_path.parent.parent / "NAMESPACE",
            _render_r_namespace(target),
            check=check,
        )
    )
    issues.extend(
        _write_or_check(
            target.r_output_path.parent.parent / "README.md",
            _render_r_readme(target),
            check=check,
        )
    )
    issues.extend(
        _write_or_check(
            target.r_output_path,
            _render_r(operations, target.catalog_function_name),
            check=check,
        )
    )
    issues.extend(
        _write_or_check(
            target.r_client_output_path,
            _render_r_client(target),
            check=check,
        )
    )
    issues.extend(
        _write_or_check(
            target.r_output_path.parent.parent
            / "man"
            / _r_package_doc_filename(target),
            _render_r_package_manual(target),
            check=check,
        )
    )
    issues.extend(
        _write_or_check(
            target.r_output_path.parent.parent / "tests" / "testthat.R",
            _render_r_tests_entrypoint(target),
            check=check,
        )
    )
    issues.extend(
        _write_or_check(
            target.r_output_path.parent.parent
            / "tests"
            / "testthat"
            / "test-client.R",
            _render_r_tests(target),
            check=check,
        )
    )
    return issues


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for generated client management."""
    parser = argparse.ArgumentParser(
        description="Generate public TS/R SDK artifacts from OpenAPI.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated outputs are stale.",
    )
    return parser.parse_args()


def main() -> int:
    """Generate SDK artifacts or fail when committed artifacts drift."""
    args = parse_args()
    issues: list[str] = []
    for target in TARGETS:
        issues.extend(_generate_target(target, check=args.check))

    if issues:
        for issue in issues:
            print(issue)
        return 1

    message = (
        "generated client artifacts are current"
        if args.check
        else "generated client artifacts updated"
    )
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
