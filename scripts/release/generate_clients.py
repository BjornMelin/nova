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

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_ROOT = REPO_ROOT / "packages" / "contracts" / "openapi"
HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head")
OPENAPI_TYPESCRIPT_VERSION = "7.13.0"
OPENAPI_TYPESCRIPT_PACKAGE = f"openapi-typescript@{OPENAPI_TYPESCRIPT_VERSION}"
_PARAM_SEGMENT = re.compile(r"^{([^{}]+)}$")
_NON_IDENTIFIER = re.compile(r"[^a-z0-9]+")
_VALID_IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


@dataclass(frozen=True)
class Operation:
    """Single public OpenAPI operation used for generated client artifacts."""

    operation_id: str
    method: str
    path: str
    summary: str | None
    has_request_body: bool
    has_required_request_body: bool
    has_path_params: bool
    has_query_params: bool
    has_required_query_params: bool
    has_header_params: bool
    has_required_header_params: bool
    request_content_types: tuple[str, ...]
    response_status_codes: tuple[int, ...]

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
    GenerationTarget(
        spec_path=OPENAPI_ROOT / "nova-auth-api.openapi.json",
        package_name="@nova/sdk-auth",
        ts_package_root=REPO_ROOT / "packages" / "nova_sdk_auth",
        client_factory_name="createNovaAuthClient",
        client_interface_name="NovaAuthClient",
        client_options_name="NovaAuthClientOptions",
        r_output_path=REPO_ROOT
        / "packages"
        / "nova_sdk_r_auth"
        / "R"
        / "generated.R",
        r_client_output_path=REPO_ROOT
        / "packages"
        / "nova_sdk_r_auth"
        / "R"
        / "client.R",
        r_client_prefix="nova_auth",
        catalog_function_name="nova_auth_operation_catalog",
    ),
)


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
            if operation.get("x-nova-sdk-visibility") == "internal":
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
                    has_path_params=("path" in parameter_index),
                    has_query_params=("query" in parameter_index),
                    has_required_query_params=_parameter_group_has_required(
                        parameter_index.get("query", ()),
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
        command = [
            "npx",
            "--yes",
            OPENAPI_TYPESCRIPT_PACKAGE,
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
                "openapi-typescript generation failed: missing `npx` command"
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
        'import type { OperationDescriptor } from "@nova/sdk-fetch/contracts";',
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
        "type ResponseBodyOf<TEntry> = TEntry extends { content: infer TContent }",
        "  ? JsonContentOf<TContent>",
        "  : null;",
        "type ResultForResponses<TResponses> = {",
        "  [TStatus in StatusCodeOf<TResponses>]: {",
        "    readonly status: TStatus;",
        "    readonly ok: TStatus extends SuccessStatus ? true : false;",
        "    readonly headers: Headers;",
        "    readonly data: ResponseBodyOf<TResponses[TStatus]>;",
        "  };",
        "}[StatusCodeOf<TResponses>];",
        "",
        "/** Named aliases for generated OpenAPI component schemas. */",
    ]

    for schema_name in schema_names:
        alias_name = _schema_alias_name(schema_name)
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
                f"export type {base_name}Result = ResultForResponses<{base_name}Responses>;",
                f'export type {base_name}ResponseData = {base_name}Result["data"];',
                f"export type {base_name}SuccessResult = Extract<{base_name}Result, {{ ok: true }}>;",
                f"export type {base_name}ErrorResult = Extract<{base_name}Result, {{ ok: false }}>;",
                f'export type {base_name}SuccessData = {base_name}SuccessResult["data"];',
                f'export type {base_name}ErrorData = {base_name}ErrorResult["data"];',
            ]
        )
        for status_code in operation.response_status_codes:
            lines.append(
                f"export type {base_name}Response{status_code} = "
                f"ResponseBodyOf<{base_name}Responses[{status_code}]>;"
            )
        lines.extend(_render_request_interface(operation))

    lines.append("")
    return "\n".join(lines)


def _render_request_interface(operation: Operation) -> list[str]:
    request_type_name = operation.request_type_name
    property_lines = _render_request_properties(operation)

    if len(operation.request_content_types) <= 1:
        lines = [f"export interface {request_type_name} {{"]
        lines.extend(f"  {line}" for line in property_lines)
        if operation.has_request_body:
            optional = "?" if not operation.has_required_request_body else ""
            lines.append(
                f"  readonly body{optional}: {_request_body_type_expression(operation)};"
            )
        lines.append("}")
        return lines

    lines = [f"export type {request_type_name} ="]
    for media_type in operation.request_content_types:
        lines.append("  | {")
        lines.extend(f"      {line}" for line in property_lines)
        lines.append(f"      readonly contentType: {json.dumps(media_type)};")
        optional = "?" if not operation.has_required_request_body else ""
        lines.append(
            f"      readonly body{optional}: "
            f"{_request_body_type_expression(operation, media_type)};"
        )
        lines.append("    }")
    lines[-1] = f"{lines[-1]};"
    return lines


def _render_request_properties(operation: Operation) -> list[str]:
    base_name = operation.type_base_name
    lines: list[str] = []
    if operation.has_path_params:
        lines.append(f"readonly pathParams: {base_name}PathParams;")
    if operation.has_query_params:
        optional = "?" if not operation.has_required_query_params else ""
        lines.append(f"readonly query{optional}: {base_name}QueryParams;")
    if operation.has_header_params:
        optional = "?" if not operation.has_required_header_params else ""
        lines.append(f"readonly headers{optional}: {base_name}Headers;")
    lines.append("readonly signal?: AbortSignal;")
    return lines


def _request_body_type_expression(
    operation: Operation,
    media_type: str | None = None,
) -> str:
    base_name = operation.type_base_name
    if media_type is None:
        return f"{base_name}RequestBody"
    body_type = (
        f"{base_name}RequestBodyForContentType<{json.dumps(media_type)}>"
    )
    if media_type == "application/x-www-form-urlencoded":
        return f"{body_type} | URLSearchParams"
    return body_type


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


def _render_typescript_errors() -> str:
    lines = [
        (
            "// Code generated by scripts/release/generate_clients.py. "
            "DO NOT EDIT."
        ),
        "",
        "interface HttpLikeResponse<TData = unknown> {",
        "  readonly status: number;",
        "  readonly ok: boolean;",
        "  readonly headers: Headers;",
        "  readonly data: TData;",
        "}",
        "",
        "/** Transport-level failure raised before an HTTP response is available. */",
        "export class NovaSdkTransportError extends Error {",
        "  readonly operationId: string;",
        "  override readonly cause: unknown;",
        "",
        "  constructor(operationId: string, cause: unknown) {",
        "    super(`Transport error for ${operationId}`);",
        '    this.name = "NovaSdkTransportError";',
        "    this.operationId = operationId;",
        "    this.cause = cause;",
        "  }",
        "}",
        "",
        "/** HTTP failure wrapper for callers that prefer throwing over branch handling. */",
        "export class NovaSdkHttpError<TResponse extends HttpLikeResponse = HttpLikeResponse> extends Error {",
        "  readonly operationId: string;",
        "  readonly response: TResponse;",
        "",
        "  constructor(operationId: string, response: TResponse) {",
        "    super(`HTTP ${response.status} for ${operationId}`);",
        '    this.name = "NovaSdkHttpError";',
        "    this.operationId = operationId;",
        "    this.response = response;",
        "  }",
        "",
        "  get status(): number {",
        "    return this.response.status;",
        "  }",
        "",
        '  get data(): TResponse["data"] {',
        "    return this.response.data;",
        "  }",
        "",
        "  get headers(): Headers {",
        "    return this.response.headers;",
        "  }",
        "}",
        "",
        "/** Throw a typed HTTP error when a response status is not successful. */",
        "export function assertOkResponse<TResponse extends HttpLikeResponse>(",
        "  operationId: string,",
        "  response: TResponse,",
        "): asserts response is TResponse & { readonly ok: true } {",
        "  if (!response.ok) {",
        "    throw new NovaSdkHttpError(operationId, response);",
        "  }",
        "}",
        "",
    ]
    return "\n".join(lines)


def _render_typescript_client(
    target: GenerationTarget,
    operations: list[Operation],
) -> str:
    request_imports = ", ".join(
        f"{operation.request_type_name}, {operation.type_base_name}Result"
        for operation in operations
    )
    lines = [
        (
            "// Code generated by scripts/release/generate_clients.py. "
            "DO NOT EDIT."
        ),
        "",
        'import { createFetchClient } from "@nova/sdk-fetch/client";',
        (
            "import type { FetchClientOptions, OperationDescriptor, PathParams, "
            'QueryParams } from "@nova/sdk-fetch/contracts";'
        ),
        'import { normalizeBaseUrl } from "@nova/sdk-fetch/url";',
        'import { NovaSdkTransportError } from "./errors.js";',
        'import { operations } from "./operations.js";',
        f'import type {{ {request_imports} }} from "./types.js";',
        "",
        "/**",
        f" * Options for configuring the generated {target.package_name} client.",
        " */",
        f"export interface {target.client_options_name} extends FetchClientOptions {{}}",
        "",
        "/**",
        f" * Generated client surface for the {target.package_name} API.",
        " */",
        f"export interface {target.client_interface_name} {{",
        "  readonly baseUrl: string;",
    ]

    for operation in operations:
        base_name = operation.type_base_name
        request_type = operation.request_type_name
        result_type = f"{base_name}Result"
        if operation.requires_request:
            lines.extend(
                [
                    "  /**",
                    f"   * Invoke the `{operation.operation_id}` operation.",
                    "   */",
                    f"  {operation.operation_id}(request: {request_type}): Promise<{result_type}>;",
                ]
            )
        else:
            lines.extend(
                [
                    "  /**",
                    f"   * Invoke the `{operation.operation_id}` operation.",
                    "   */",
                    f"  {operation.operation_id}(request?: {request_type}): Promise<{result_type}>;",
                ]
            )
    lines.extend(
        [
            "}",
            "",
            "type OperationRequest = {",
            "  readonly body?: unknown;",
            "  readonly contentType?: string;",
            "  readonly headers?: HeadersInit;",
            "  readonly pathParams?: PathParams;",
            "  readonly query?: QueryParams;",
            "  readonly signal?: AbortSignal;",
            "};",
            "",
            "async function executeOperation<TResult>(",
            "  fetchClient: ReturnType<typeof createFetchClient>,",
            "  operation: OperationDescriptor,",
            "  request: OperationRequest = {},",
            "  defaultContentType?: string,",
            "): Promise<TResult> {",
            "  try {",
            "    return (await fetchClient.request<unknown>(operation, {",
            "      body: request.body,",
            "      contentType: request.contentType ?? defaultContentType,",
            "      headers: request.headers,",
            "      pathParams: request.pathParams,",
            "      query: request.query,",
            "      signal: request.signal,",
            "    })) as TResult;",
            "  } catch (error) {",
            "    throw new NovaSdkTransportError(operation.operationId, error);",
            "  }",
            "}",
            "",
            "/**",
            f" * Create a generated client for the {target.package_name} API.",
            " *",
            " * @param options - Transport and base URL options for the client.",
            f" * @returns A configured {target.client_interface_name} instance.",
            " */",
            f"export function {target.client_factory_name}(",
            f"  options: {target.client_options_name},",
            f"): {target.client_interface_name} {{",
            "  const fetchClient = createFetchClient(options);",
            "  const baseUrl = normalizeBaseUrl(options.baseUrl);",
            "",
            "  return {",
            "    baseUrl,",
        ]
    )

    for operation in operations:
        base_name = operation.type_base_name
        request_type = operation.request_type_name
        result_type = f"{base_name}Result"
        if operation.requires_request:
            signature = f"{operation.operation_id}(request: {request_type})"
            request_expr = "request"
        else:
            signature = f"{operation.operation_id}(request?: {request_type})"
            request_expr = "request ?? {}"
        lines.extend(
            [
                "    /**",
                f"     * Invoke the `{operation.operation_id}` operation.",
                "     */",
                f"    async {signature}: Promise<{result_type}> {{",
                f"      return executeOperation<{result_type}>(",
                "        fetchClient,",
                f"        operations.{operation.operation_id},",
                f"        {request_expr} as OperationRequest,",
                (
                    f"        {json.dumps(operation.default_request_content_type)},"
                    if operation.default_request_content_type is not None
                    else "        undefined,"
                ),
                "      );",
                "    },",
            ]
        )

    lines.extend(["  };", "}", ""])
    return "\n".join(lines)


def _render_r(operations: list[Operation], catalog_function_name: str) -> str:
    lines = [
        "# Code generated by scripts/release/generate_clients.py. DO NOT EDIT.",
        "",
        f"{catalog_function_name} <- function() {{",
        "  list(",
    ]

    for index, operation in enumerate(operations):
        suffix = "," if index < len(operations) - 1 else ""
        summary_value = (
            json.dumps(operation.summary) if operation.summary else "NULL"
        )
        lines.extend(
            [
                f'    "{operation.operation_id}" = list(',
                f'      operation_id = "{operation.operation_id}",',
                f'      method = "{operation.method}",',
                f'      path = "{operation.path}",',
                f"      summary = {summary_value}",
                f"    ){suffix}",
            ]
        )

    lines.extend(["  )", "}", ""])
    return "\n".join(lines)


def _render_r_client(target: GenerationTarget) -> str:
    client_constructor = f"new_{target.r_client_prefix}_client"
    descriptor_function = f"{target.r_client_prefix}_request_descriptor"
    lines = [
        "# Code generated by scripts/release/generate_clients.py. DO NOT EDIT.",
        "",
        f"{client_constructor} <- function(base_url, timeout_seconds = 30) {{",
        (
            "  if (!is.character(base_url) || length(base_url) != 1L || "
            "!nzchar(base_url)) {"
        ),
        '    stop("base_url must be a non-empty string", call. = FALSE)',
        "  }",
        (
            "  if (is.null(timeout_seconds) || !is.numeric(timeout_seconds) || "
            "length(timeout_seconds) != 1L || is.na(timeout_seconds) || "
            "!is.finite(timeout_seconds) || timeout_seconds <= 0) {"
        ),
        (
            '    stop("timeout_seconds must be a finite positive number", '
            "call. = FALSE)"
        ),
        "  }",
        "  structure(",
        "    list(",
        '      base_url = sub("/+$", "", base_url),',
        "      timeout_seconds = timeout_seconds,",
        f"      operations = {target.catalog_function_name}()",
        "    ),",
        f'    class = "{target.r_client_prefix}_client"',
        "  )",
        "}",
        "",
        (
            f"{descriptor_function} <- function("
            "client, operation_id, path_params = list(), query = list()) {"
        ),
        "  operation <- client$operations[[operation_id]]",
        "  if (is.null(operation)) {",
        (
            '    stop(sprintf("unknown operation_id: %s", operation_id), '
            "call. = FALSE)"
        ),
        "  }",
        "",
        "  resolved_path <- operation$path",
        "  if (length(path_params) > 0L) {",
        "    for (param_name in names(path_params)) {",
        "      resolved_path <- gsub(",
        '        sprintf("{%s}", param_name),',
        (
            "        utils::URLencode("
            "as.character(path_params[[param_name]]), reserved = TRUE),"
        ),
        "        resolved_path,",
        "        fixed = TRUE",
        "      )",
        "    }",
        "  }",
        (
            "  missing_path_params <- regmatches("
            'resolved_path, gregexpr("\\\\{[^}]+\\\\}", resolved_path,'
            " perl = TRUE)"
            ")[[1]]"
        ),
        "  if (length(missing_path_params) > 0L) {",
        (
            "    stop(sprintf("
            '"missing path parameter(s) for %s: %s", '
            'operation_id, paste(missing_path_params, collapse = ", ")), '
            "call. = FALSE)"
        ),
        "  }",
        "",
        "  list(",
        "    operation_id = operation$operation_id,",
        "    method = operation$method,",
        "    url = paste0(client$base_url, resolved_path),",
        "    query = query,",
        "    timeout_seconds = client$timeout_seconds",
        "  )",
        "}",
        "",
    ]
    return "\n".join(lines)


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
    issues.extend(
        _write_or_check(
            target.ts_package_root / "src" / "errors.ts",
            _render_typescript_errors(),
            check=check,
        )
    )
    issues.extend(
        _write_or_check(
            target.ts_package_root / "src" / "client.ts",
            _render_typescript_client(target, operations),
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
