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
    GenerationTarget(
        spec_path=OPENAPI_ROOT / "nova-auth-api.openapi.json",
        package_name="@nova/sdk-auth",
        ts_package_root=REPO_ROOT / "packages" / "nova_sdk_auth",
        client_factory_name="createNovaAuthClient",
        client_interface_name="NovaAuthClient",
        client_options_name="NovaAuthClientOptions",
        r_package_name="nova.sdk.r.auth",
        r_package_title="Nova SDK R auth client",
        r_package_description="Generated R client for the Nova auth API.",
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
        lines.extend(
            f"export type {base_name}Response{status_code} = "
            f"ResponseBodyOf<{base_name}Responses[{status_code}]>;"
            for status_code in operation.response_status_codes
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


def _r_exported_function_names(prefix: str) -> tuple[str, ...]:
    """Return the exported R function names for a client prefix."""
    return (
        f"create_{prefix}_client",
        f"{prefix}_operation_catalog",
        f"{prefix}_request_descriptor",
        f"{prefix}_execute_operation",
        f"{prefix}_decode_error_envelope",
    )


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
        f"{catalog_function_name} <- function() {{",
        "  list(",
    ]

    for index, operation in enumerate(operations):
        suffix = "," if index < len(operations) - 1 else ""
        summary_value = (
            json.dumps(operation.summary) if operation.summary else "NULL"
        )
        request_content_types = (
            "c("
            + ", ".join(
                json.dumps(media_type)
                for media_type in operation.request_content_types
            )
            + ")"
            if operation.request_content_types
            else "character(0)"
        )
        response_status_codes = (
            "c("
            + ", ".join(f"{code}L" for code in operation.response_status_codes)
            + ")"
            if operation.response_status_codes
            else "integer(0)"
        )
        lines.extend(
            [
                f'    "{operation.operation_id}" = list(',
                f'      operation_id = "{operation.operation_id}",',
                f'      method = "{operation.method}",',
                f'      path = "{operation.path}",',
                f"      summary = {summary_value},",
                f"      has_request_body = {'TRUE' if operation.has_request_body else 'FALSE'},",
                f"      has_required_request_body = {'TRUE' if operation.has_required_request_body else 'FALSE'},",
                f"      has_path_params = {'TRUE' if operation.has_path_params else 'FALSE'},",
                f"      has_query_params = {'TRUE' if operation.has_query_params else 'FALSE'},",
                f"      has_required_query_params = {'TRUE' if operation.has_required_query_params else 'FALSE'},",
                f"      has_header_params = {'TRUE' if operation.has_header_params else 'FALSE'},",
                f"      has_required_header_params = {'TRUE' if operation.has_required_header_params else 'FALSE'},",
                f"      request_content_types = {request_content_types},",
                f"      default_request_content_type = {json.dumps(operation.default_request_content_type) if operation.default_request_content_type is not None else 'NULL'},",
                f"      response_status_codes = {response_status_codes}",
                f"    ){suffix}",
            ]
        )

    lines.extend(
        [
            "  )",
            "}",
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
            f"{prefix}_select_content_type <- function(operation, content_type) {{",
            "  available_content_types <- operation$request_content_types",
            "  if (is.null(content_type) || !nzchar(as.character(content_type)[[1]])) {",
            "    if (length(available_content_types) == 0L) {",
            "      return(NULL)",
            "    }",
            "    if (length(available_content_types) > 1L) {",
            '      stop(sprintf("operation %s requires an explicit content_type", operation$operation_id), call. = FALSE)',
            "    }",
            "    return(available_content_types[[1L]])",
            "  }",
            "  selected_content_type <- as.character(content_type)[[1]]",
            "  if (!(selected_content_type %in% available_content_types)) {",
            '    stop(sprintf("unsupported content_type %s for operation %s", selected_content_type, operation$operation_id), call. = FALSE)',
            "  }",
            "  selected_content_type",
            "}",
            "",
            f"{prefix}_parse_json_body <- function(body) {{",
            "  if (is.null(body) || !nzchar(trimws(body))) {",
            "    return(NULL)",
            "  }",
            "  tryCatch(",
            "    jsonlite::fromJSON(body, simplifyVector = FALSE),",
            "    error = function(...) NULL",
            "  )",
            "}",
            "",
            f"{prefix}_encode_json_body <- function(body) {{",
            '  jsonlite::toJSON(body, auto_unbox = TRUE, null = "null")',
            "}",
            "",
            f"{prefix}_encode_form_body <- function(body) {{",
            "  if (is.null(body) || length(body) == 0L) {",
            '    return("")',
            "  }",
            f'  body <- {prefix}_normalize_named_list(body, "body")',
            "  encode_item <- function(name, value) {",
            "    if (is.null(value)) {",
            "      return(character(0))",
            "    }",
            '    if (is.list(value) && !inherits(value, "data.frame")) {',
            '      value <- jsonlite::toJSON(value, auto_unbox = TRUE, null = "null")',
            '      return(paste0(utils::URLencode(name, reserved = TRUE), "=", utils::URLencode(value, reserved = TRUE)))',
            "    }",
            "    values <- as.character(value)",
            "    if (length(values) == 0L) {",
            "      return(character(0))",
            "    }",
            "    encoded_name <- utils::URLencode(name, reserved = TRUE)",
            "    vapply(",
            "      values,",
            "      function(item) {",
            '        paste0(encoded_name, "=", utils::URLencode(item, reserved = TRUE))',
            "      },",
            "      character(1)",
            "    )",
            "  }",
            "  parts <- character(0)",
            "  for (name in names(body)) {",
            "    parts <- c(parts, encode_item(name, body[[name]]))",
            "  }",
            '  paste(parts, collapse = "&")',
            "}",
            "",
            f"{prefix}_encode_request_body <- function(body, content_type) {{",
            "  if (is.null(body)) {",
            "    return(NULL)",
            "  }",
            '  if (identical(content_type, "application/json")) {',
            f"    return({prefix}_encode_json_body(body))",
            "  }",
            '  if (identical(content_type, "application/x-www-form-urlencoded")) {',
            f"    return({prefix}_encode_form_body(body))",
            "  }",
            '  stop(sprintf("unsupported content_type %s", content_type), call. = FALSE)',
            "}",
            "",
            f"{prefix}_decode_error_envelope <- function(body, status = NULL) {{",
            f"  parsed_body <- {prefix}_parse_json_body(body)",
            "  if (!is.list(parsed_body) || is.null(parsed_body$error) || !is.list(parsed_body$error)) {",
            "    if (is.null(status)) {",
            "      return(NULL)",
            "    }",
            "    fallback_message <- if (is.null(body) || !nzchar(trimws(body))) {",
            '      sprintf("HTTP %s response", status)',
            "    } else {",
            "      body",
            "    }",
            "    return(",
            "      list(",
            "        error = list(",
            '          code = paste0("http_", status),',
            "          message = fallback_message,",
            "          details = list(),",
            "          request_id = NULL",
            "        )",
            "      )",
            "    )",
            "  }",
            "  error_body <- parsed_body$error",
            "  request_id <- error_body$request_id",
            "  if (length(request_id) == 0L) {",
            "    request_id <- NULL",
            "  }",
            "  list(",
            "    error = list(",
            "      code = as.character(error_body$code),",
            "      message = as.character(error_body$message),",
            f"      details = {prefix}_null_coalesce(error_body$details, list()),",
            "      request_id = request_id",
            "    )",
            "  )",
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def _render_r_client(target: GenerationTarget) -> str:
    prefix = target.r_client_prefix
    client_constructor = f"create_{prefix}_client"
    request_descriptor = f"{prefix}_request_descriptor"
    request_executor = f"{prefix}_execute_operation"
    default_performer = f"{prefix}_default_request_performer"
    lines = [
        "# Code generated by scripts/release/generate_clients.py. DO NOT EDIT.",
        "",
        f"{default_performer} <- function(request) {{",
        "  if (!is.list(request)) {",
        '    stop("request must be a list", call. = FALSE)',
        "  }",
        "  http_request <- httr2::request(request$url)",
        "  http_request <- httr2::req_method(http_request, request$method)",
        "  if (length(request$query) > 0L) {",
        "    http_request <- do.call(httr2::req_url_query, c(list(http_request), request$query))",
        "  }",
        "  if (length(request$headers) > 0L) {",
        "    http_request <- do.call(httr2::req_headers, c(list(http_request), request$headers))",
        "  }",
        "  http_request <- httr2::req_options(http_request, timeout = request$timeout_seconds)",
        f"  encoded_body <- {prefix}_encode_request_body(request$body, request$content_type)",
        "  if (!is.null(encoded_body)) {",
        "    http_request <- httr2::req_body_raw(http_request, charToRaw(encoded_body))",
        "    http_request <- do.call(",
        "      httr2::req_headers,",
        "      c(",
        "        list(http_request),",
        '        list("Content-Type" = request$content_type)',
        "      )",
        "    )",
        "  }",
        "  http_request <- httr2::req_error(http_request, is_error = ~ FALSE)",
        "  response <- httr2::req_perform(http_request)",
        "  list(",
        "    status = httr2::resp_status(response),",
        "    headers = httr2::resp_headers(response),",
        "    body = httr2::resp_body_string(response),",
        "    url = request$url",
        "  )",
        "}",
        "",
        f"{request_descriptor} <- function(",
        "  client,",
        "  operation_id,",
        "  body = NULL,",
        "  path_params = NULL,",
        "  query = NULL,",
        "  headers = NULL,",
        "  content_type = NULL",
        ") {",
        "  if (!is.list(client) || is.null(client$operations)) {",
        '    stop("client must be created by the package constructor", call. = FALSE)',
        "  }",
        "  operation <- client$operations[[operation_id]]",
        "  if (is.null(operation)) {",
        '    stop(sprintf("unknown operation_id: %s", operation_id), call. = FALSE)',
        "  }",
        f'  path_params <- {prefix}_normalize_named_list(path_params, "path_params")',
        f'  query <- {prefix}_normalize_named_list(query, "query")',
        f'  request_headers <- {prefix}_normalize_named_list(headers, "headers")',
        "  merged_headers <- c(client$default_headers, request_headers)",
        "  if (length(merged_headers) > 0L) {",
        "    merged_headers <- merged_headers[!duplicated(names(merged_headers), fromLast = TRUE)]",
        "  }",
        f"  merged_headers <- {prefix}_prune_null_headers(merged_headers)",
        f"  resolved_path <- {prefix}_resolve_path(operation$path, path_params)",
        f"  selected_content_type <- {prefix}_select_content_type(operation, content_type)",
        "  if (is.null(body)) {",
        "    if (isTRUE(operation$has_request_body) && isTRUE(operation$has_required_request_body)) {",
        '      stop(sprintf("operation %s requires a request body", operation_id), call. = FALSE)',
        "    }",
        "  } else if (!isTRUE(operation$has_request_body)) {",
        '    stop(sprintf("operation %s does not accept a request body", operation_id), call. = FALSE)',
        "  }",
        "  list(",
        "    operation_id = operation$operation_id,",
        "    method = operation$method,",
        "    path = resolved_path,",
        "    url = paste0(client$base_url, resolved_path),",
        "    body = body,",
        "    content_type = selected_content_type,",
        "    headers = merged_headers,",
        "    query = query,",
        "    timeout_seconds = client$timeout_seconds",
        "  )",
        "}",
        "",
        f"{request_executor} <- function(",
        "  client,",
        "  operation_id,",
        "  body = NULL,",
        "  path_params = NULL,",
        "  query = NULL,",
        "  headers = NULL,",
        "  content_type = NULL",
        ") {",
        f"  request <- {request_descriptor}(",
        "    client = client,",
        "    operation_id = operation_id,",
        "    body = body,",
        "    path_params = path_params,",
        "    query = query,",
        "    headers = headers,",
        "    content_type = content_type",
        "  )",
        "  response <- tryCatch(",
        "    client$request_performer(request),",
        "    error = function(error) {",
        "      stop(",
        "        sprintf(",
        '          "request_performer failed for %s: %s",',
        "          operation_id,",
        "          conditionMessage(error)",
        "        ),",
        "        call. = FALSE",
        "      )",
        "    }",
        "  )",
        "  if (!is.list(response) || is.null(response$status)) {",
        '    stop("request_performer must return a list with status", call. = FALSE)',
        "  }",
        "  status <- as.integer(response$status[[1]])",
        "  if (is.na(status)) {",
        '    stop("request_performer returned an invalid status code", call. = FALSE)',
        "  }",
        "  body_text <- response$body",
        "  if (is.null(body_text)) {",
        '    body_text <- ""',
        "  }",
        "  ok <- status >= 200L && status < 300L",
        "  if (ok) {",
        f"    data <- {prefix}_parse_json_body(body_text)",
        "    error <- NULL",
        "  } else {",
        "    data <- NULL",
        f"    error <- {prefix}_decode_error_envelope(body_text, status = status)",
        "  }",
        "  list(",
        "    ok = ok,",
        "    status = status,",
        "    headers = response$headers,",
        "    data = data,",
        "    error = error,",
        "    request = request,",
        "    response = response",
        "  )",
        "}",
        "",
        f"{client_constructor} <- function(",
        "  base_url,",
        f"  request_performer = {default_performer},",
        "  default_headers = NULL,",
        "  timeout_seconds = 30",
        ") {",
        f"  base_url <- {prefix}_normalize_base_url(base_url)",
        "  if (!is.function(request_performer)) {",
        '    stop("request_performer must be a function", call. = FALSE)',
        "  }",
        "  if (!is.numeric(timeout_seconds) || length(timeout_seconds) != 1L || is.na(timeout_seconds) || !is.finite(timeout_seconds) || timeout_seconds <= 0) {",
        '    stop("timeout_seconds must be a finite positive number", call. = FALSE)',
        "  }",
        f'  default_headers <- {prefix}_normalize_named_list(default_headers, "default_headers")',
        f"  operations <- {target.catalog_function_name}()",
        "  client <- list(",
        "    base_url = base_url,",
        "    request_performer = request_performer,",
        "    default_headers = default_headers,",
        "    timeout_seconds = timeout_seconds,",
        "    operations = operations",
        "  )",
        "  for (operation_id in names(operations)) {",
        "    client[[operation_id]] <- local({",
        "      bound_operation_id <- operation_id",
        "      function(",
        "        body = NULL,",
        "        path_params = NULL,",
        "        query = NULL,",
        "        headers = NULL,",
        "        content_type = NULL",
        "      ) {",
        f"        {request_executor}(",
        "          client = client,",
        "          operation_id = bound_operation_id,",
        "          body = body,",
        "          path_params = path_params,",
        "          query = query,",
        "          headers = headers,",
        "          content_type = content_type",
        "        )",
        "      }",
        "    })",
        "  }",
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
        "RoxygenNote: 7.3.2",
        "Imports:",
        "    httr2,",
        "    jsonlite",
        "Suggests:",
        "    testthat (>= 3.0.0)",
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
    exports = _r_exported_function_names(target.r_client_prefix)
    lines = [
        "# Generated by roxygen2: do not edit by hand",
        "",
    ]
    lines.extend(f"export({name})" for name in exports)
    lines.append("")
    return "\n".join(lines)


def _render_r_readme(
    target: GenerationTarget, operations: list[Operation]
) -> str:
    constructor = f"create_{target.r_client_prefix}_client"
    request_descriptor = f"{target.r_client_prefix}_request_descriptor"
    operation_catalog = target.catalog_function_name
    lines = [
        f"# `{target.r_package_name}`",
        "",
        f"Generated R client for the Nova {target.r_client_prefix.removeprefix('nova_')} API.",
        "",
        "This package is generated from committed OpenAPI and is kept in-repo so",
        "Nova release tooling can build and check the real package tree.",
        "",
        "## Surface",
        "",
        f"- `{constructor}`",
        f"- `{operation_catalog}`",
        f"- `{request_descriptor}`",
        f"- `{target.r_client_prefix}_execute_operation`",
        f"- `{target.r_client_prefix}_decode_error_envelope`",
        "",
        "## Example",
        "",
        "```r",
    ]
    if target.r_client_prefix == "nova_file":
        lines.extend(
            [
                "client <- create_nova_file_client(",
                '  "https://nova.example/",',
                "  default_headers = list(",
                '    "Idempotency-Key" = "req-123"',
                "  )",
                ")",
                "",
                "result <- client$create_job(",
                "  body = list(",
                '    job_type = "transfer.process",',
                '    payload = list(upload_key = "session-abc123/sample.csv"),',
                '    session_id = "session-abc123"',
                "  )",
                ")",
                "result$data$job$job_id",
            ]
        )
    else:
        lines.extend(
            [
                'client <- create_nova_auth_client("https://nova.example/")',
                "",
                "result <- client$verify_token(",
                "  body = list(",
                '    access_token = "token-123",',
                '    required_scopes = c("files:write"),',
                "    required_permissions = character(0)",
                "  )",
                ")",
                "result$data$principal$subject",
            ]
        )
    lines.extend(["```", ""])
    return "\n".join(lines)


def _render_r_package_manual(target: GenerationTarget) -> str:
    exports = _r_exported_function_names(target.r_client_prefix)
    constructor = f"create_{target.r_client_prefix}_client"
    request_descriptor = f"{target.r_client_prefix}_request_descriptor"
    execute_operation = f"{target.r_client_prefix}_execute_operation"
    decode_error_envelope = f"{target.r_client_prefix}_decode_error_envelope"
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
            f"  {constructor}(base_url, request_performer = {target.r_client_prefix}_default_request_performer, default_headers = NULL, timeout_seconds = 30)",
            f"  {target.catalog_function_name}()",
            f"  {request_descriptor}(client, operation_id, body = NULL, path_params = NULL, query = NULL, headers = NULL, content_type = NULL)",
            f"  {execute_operation}(client, operation_id, body = NULL, path_params = NULL, query = NULL, headers = NULL, content_type = NULL)",
            f"  {decode_error_envelope}(body, status = NULL)",
            "}",
            "",
            "\\arguments{",
            "  \\item{base_url}{Base URL for the Nova API, without a trailing slash requirement.}",
            "  \\item{request_performer}{Function used to execute a prepared request descriptor.}",
            "  \\item{default_headers}{Named list of default request headers applied to every request.}",
            "  \\item{timeout_seconds}{Positive request timeout in seconds.}",
            "  \\item{client}{Client instance created by the package constructor.}",
            "  \\item{operation_id}{Stable Nova operation identifier from the operation catalog.}",
            "  \\item{body}{Optional request body payload for operations that accept one.}",
            "  \\item{path_params}{Named list of path parameter values used to resolve templated routes.}",
            "  \\item{query}{Named list of query-string parameters.}",
            "  \\item{headers}{Named list of per-request headers merged over default headers.}",
            "  \\item{content_type}{Explicit request media type for multi-media operations.}",
            "  \\item{status}{Optional HTTP status code used when decoding an error envelope.}",
            "}",
            "",
            "\\value{",
            "  The constructor returns a client object with bound operation methods.",
            "  The request descriptor returns a structured request list.",
            "  The executor returns a structured response list with parsed data or error envelopes.",
            "}",
            "",
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


def _render_r_tests(
    target: GenerationTarget, operations: list[Operation]
) -> str:
    prefix = target.r_client_prefix
    constructor = f"create_{prefix}_client"
    request_descriptor = f"{prefix}_request_descriptor"
    if prefix == "nova_file":
        lines = [
            'test_that("operation catalog exposes public operations", {',
            f"  catalog <- {target.catalog_function_name}()",
            "  expect_true(is.list(catalog))",
            '  expect_true("create_job" %in% names(catalog))',
            '  expect_false("update_job_result" %in% names(catalog))',
            '  expect_identical(catalog$create_job$request_content_types, "application/json")',
            "})",
            "",
            'test_that("request descriptors resolve paths, query params, and headers", {',
            f'  client <- {constructor}("https://nova.example/", request_performer = function(request) {{',
            '    list(status = 200L, headers = list(), body = \'{"job":{"job_id":"job-0001","status":"running"}}\', url = request$url)',
            "  })",
            f'  descriptor <- {request_descriptor}(client, "get_job_status", path_params = list(job_id = "job-123"), query = list(limit = 5), headers = list("Idempotency-Key" = "req-123"))',
            '  expect_equal(descriptor$url, "https://nova.example/v1/jobs/job-123")',
            "  expect_equal(descriptor$query$limit, 5)",
            '  expect_equal(descriptor$headers[["Idempotency-Key"]], "req-123")',
            "  expect_true(is.null(descriptor$body))",
            "  expect_equal(descriptor$content_type, NULL)",
            "})",
            "",
            'test_that("client methods execute requests and decode success and error envelopes", {',
            "  captured_requests <- list()",
            f'  client <- {constructor}("https://nova.example/", request_performer = function(request) {{',
            "    captured_requests[[length(captured_requests) + 1L]] <<- request",
            '    list(status = 200L, headers = list(), body = \'{"job":{"job_id":"job-0001","status":"pending"}}\', url = request$url)',
            "  })",
            '  result <- client$create_job(body = list(job_type = "transfer.process", payload = list(upload_key = "session-abc123/sample.csv"), session_id = "session-abc123"), headers = list("Idempotency-Key" = "req-123"))',
            "  expect_true(result$ok)",
            '  expect_equal(result$data$job$job_id, "job-0001")',
            '  expect_equal(captured_requests[[1]]$content_type, "application/json")',
            '  expect_equal(captured_requests[[1]]$headers[["Idempotency-Key"]], "req-123")',
            '  expect_equal(captured_requests[[1]]$body$job_type, "transfer.process")',
            "",
            f'  failing_client <- {constructor}("https://nova.example/", request_performer = function(request) {{',
            '    list(status = 503L, headers = list(), body = \'{"error":{"code":"queue_unavailable","message":"jobs queue unavailable","details":{"backend":"sqs"},"request_id":"req-jobs-503"}}\', url = request$url)',
            "  })",
            '  error_result <- failing_client$create_job(body = list(job_type = "transfer.process", payload = list(upload_key = "session-abc123/sample.csv"), session_id = "session-abc123"))',
            "  expect_false(error_result$ok)",
            '  expect_equal(error_result$error$error$code, "queue_unavailable")',
            "})",
            "",
        ]
    else:
        lines = [
            'test_that("operation catalog exposes multi-media operations", {',
            f"  catalog <- {target.catalog_function_name}()",
            "  expect_true(is.list(catalog))",
            '  expect_true("introspect_token" %in% names(catalog))',
            '  expect_identical(catalog$verify_token$request_content_types, "application/json")',
            '  expect_identical(catalog$introspect_token$request_content_types, c("application/json", "application/x-www-form-urlencoded"))',
            "})",
            "",
            'test_that("request descriptors require explicit content types for multi-media bodies", {',
            f'  client <- {constructor}("https://nova.example/", request_performer = function(request) {{',
            '    list(status = 200L, headers = list(), body = \'{"principal":{"subject":"auth0|user-123","scope_id":"tenant-acme","tenant_id":"tenant-acme","scopes":["files:write","jobs:enqueue"],"permissions":["jobs:enqueue","jobs:read"]},"claims":{"iss":"https://example.us.auth0.com/","aud":"nova-file-api","sub":"auth0|user-123","exp":1999999999,"iat":1999999000,"scope":"files:write jobs:enqueue"}}\', url = request$url)',
            "  })",
            "  expect_error(",
            f'    {request_descriptor}(client, "introspect_token", body = list(access_token = "token-123", required_scopes = c("files:write"), required_permissions = character(0))),',
            '    "requires an explicit content_type"',
            "  )",
            f'  json_descriptor <- {request_descriptor}(client, "introspect_token", body = list(access_token = "token-123", required_scopes = c("files:write"), required_permissions = character(0)), content_type = "application/json")',
            '  expect_equal(json_descriptor$content_type, "application/json")',
            f'  form_descriptor <- {request_descriptor}(client, "introspect_token", body = list(token = "token-123", required_scopes = c("files:write"), required_permissions = character(0)), content_type = "application/x-www-form-urlencoded")',
            '  expect_equal(form_descriptor$content_type, "application/x-www-form-urlencoded")',
            '  expect_equal(form_descriptor$body$token, "token-123")',
            "})",
            "",
            'test_that("client methods execute requests and decode success and error envelopes", {',
            "  captured_requests <- list()",
            f'  client <- {constructor}("https://nova.example/", request_performer = function(request) {{',
            "    captured_requests[[length(captured_requests) + 1L]] <<- request",
            '    list(status = 200L, headers = list(), body = \'{"principal":{"subject":"auth0|user-123","scope_id":"tenant-acme","tenant_id":"tenant-acme","scopes":["files:write","jobs:enqueue"],"permissions":["jobs:enqueue","jobs:read"]},"claims":{"iss":"https://example.us.auth0.com/","aud":"nova-file-api","sub":"auth0|user-123","exp":1999999999,"iat":1999999000,"scope":"files:write jobs:enqueue"}}\', url = request$url)',
            "  })",
            '  result <- client$verify_token(body = list(access_token = "token-123", required_scopes = c("files:write"), required_permissions = character(0)))',
            "  expect_true(result$ok)",
            '  expect_equal(result$data$principal$subject, "auth0|user-123")',
            '  expect_equal(captured_requests[[1]]$body$access_token, "token-123")',
            "",
            f'  failing_client <- {constructor}("https://nova.example/", request_performer = function(request) {{',
            '    list(status = 401L, headers = list(), body = \'{"error":{"code":"invalid_token","message":"token validation failed","details":{},"request_id":"req-auth-401"}}\', url = request$url)',
            "  })",
            '  error_result <- failing_client$verify_token(body = list(access_token = "token-123", required_scopes = character(0), required_permissions = character(0)))',
            "  expect_false(error_result$ok)",
            '  expect_equal(error_result$error$error$code, "invalid_token")',
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
            _render_r_readme(target, operations),
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
            _render_r_tests(target, operations),
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
