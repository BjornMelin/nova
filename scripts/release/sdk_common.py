#!/usr/bin/env python3
"""Shared helpers for Nova SDK generation entrypoints."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_ROOT = REPO_ROOT / "packages" / "contracts" / "openapi"
FULL_OPENAPI_ARTIFACT_NAME = "nova-file-api.openapi.json"
PUBLIC_OPENAPI_ARTIFACT_NAME = "nova-file-api.public.openapi.json"
FULL_OPENAPI_SPEC_PATH = OPENAPI_ROOT / FULL_OPENAPI_ARTIFACT_NAME
PUBLIC_OPENAPI_SPEC_PATH = OPENAPI_ROOT / PUBLIC_OPENAPI_ARTIFACT_NAME
HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head")
_PARAM_SEGMENT = re.compile(r"^{([^{}]+)}$")
_NON_IDENTIFIER = re.compile(r"[^a-z0-9]+")
SDK_VISIBILITY_EXTENSION = "x-nova-sdk-visibility"
SDK_VISIBILITY_INTERNAL = "internal"


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


@dataclass(frozen=True)
class GenerationTarget:
    """Output targets for one committed OpenAPI document."""

    spec_path: Path
    ts_package_root: Path
    r_package_name: str
    r_package_title: str
    r_package_description: str
    r_output_path: Path
    r_client_output_path: Path
    r_client_prefix: str
    catalog_function_name: str


TARGETS = (
    GenerationTarget(
        spec_path=PUBLIC_OPENAPI_SPEC_PATH,
        ts_package_root=REPO_ROOT / "packages" / "nova_sdk_ts",
        r_package_name="nova",
        r_package_title="Nova R client",
        r_package_description="Thin httr2 client for the Nova public API.",
        r_output_path=REPO_ROOT
        / "packages"
        / "nova_sdk_r"
        / "R"
        / "generated.R",
        r_client_output_path=REPO_ROOT
        / "packages"
        / "nova_sdk_r"
        / "R"
        / "client.R",
        r_client_prefix="nova",
        catalog_function_name="nova_operation_catalog",
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


def _resolve_local_ref(spec: dict[str, Any], ref: str) -> Any:
    if not ref.startswith("#/"):
        raise ValueError(f"Unsupported OpenAPI reference: {ref!r}")

    current: Any = spec
    for segment in ref[2:].split("/"):
        if not isinstance(current, dict) or segment not in current:
            raise ValueError(f"Missing referenced OpenAPI node: {ref}")
        current = current[segment]
    return current


def _clone_json_compatible(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _collect_component_refs(
    node: Any,
    refs: set[tuple[str, str]],
) -> None:
    if isinstance(node, list):
        for item in node:
            _collect_component_refs(item, refs)
        return

    if not isinstance(node, dict):
        return

    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/"):
        parts = ref.split("/")
        if len(parts) >= 4:
            refs.add((parts[2], parts[3]))

    for value in node.values():
        _collect_component_refs(value, refs)


def _collect_security_scheme_names(node: Any) -> set[str]:
    names: set[str] = set()
    if not isinstance(node, list):
        return names
    for requirement in node:
        if isinstance(requirement, dict):
            names.update(
                str(name)
                for name in requirement
                if isinstance(name, str) and name
            )
    return names


def _build_public_paths(
    spec: dict[str, Any],
) -> tuple[dict[str, Any], set[tuple[str, str]], set[str]]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise TypeError("OpenAPI spec missing paths object")

    public_paths: dict[str, Any] = {}
    refs: set[tuple[str, str]] = set()
    security_scheme_names = _collect_security_scheme_names(spec.get("security"))

    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, dict):
            continue
        public_path_item: dict[str, Any] = {}
        has_public_operation = False

        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                continue
            if (
                operation.get(SDK_VISIBILITY_EXTENSION)
                == SDK_VISIBILITY_INTERNAL
            ):
                continue
            has_public_operation = True
            cloned_operation = _clone_json_compatible(operation)
            public_path_item[method] = cloned_operation
            _collect_component_refs(cloned_operation, refs)
            security_scheme_names.update(
                _collect_security_scheme_names(operation.get("security"))
            )

        if not has_public_operation:
            continue

        for key, value in path_item.items():
            if key in HTTP_METHODS:
                continue
            cloned_value = _clone_json_compatible(value)
            public_path_item[key] = cloned_value
            _collect_component_refs(cloned_value, refs)
            if key == "security":
                security_scheme_names.update(
                    _collect_security_scheme_names(value)
                )

        public_paths[path] = public_path_item

    return public_paths, refs, security_scheme_names


def _build_public_components(
    spec: dict[str, Any],
    *,
    refs: set[tuple[str, str]],
    security_scheme_names: set[str],
) -> dict[str, Any]:
    components = spec.get("components")
    if not isinstance(components, dict):
        return {}

    public_components: dict[str, dict[str, Any]] = {}
    pending = list(refs)
    visited: set[tuple[str, str]] = set()

    while pending:
        component_kind, component_name = pending.pop()
        if (component_kind, component_name) in visited:
            continue
        visited.add((component_kind, component_name))

        component_group = components.get(component_kind)
        if not isinstance(component_group, dict):
            raise TypeError(
                f"Missing OpenAPI component group {component_kind!r}"
            )
        component_value = component_group.get(component_name)
        if component_value is None:
            raise ValueError(
                "Missing referenced OpenAPI component "
                f"#/components/{component_kind}/{component_name}"
            )
        cloned_value = _clone_json_compatible(component_value)
        public_components.setdefault(component_kind, {})[component_name] = (
            cloned_value
        )

        nested_refs: set[tuple[str, str]] = set()
        _collect_component_refs(cloned_value, nested_refs)
        pending.extend(sorted(nested_refs - visited))

    if security_scheme_names:
        security_schemes = components.get("securitySchemes")
        if isinstance(security_schemes, dict):
            for name in sorted(security_scheme_names):
                value = security_schemes.get(name)
                if value is not None:
                    public_components.setdefault("securitySchemes", {})[
                        name
                    ] = _clone_json_compatible(value)

    return public_components


def _build_public_openapi_spec(spec: dict[str, Any]) -> dict[str, Any]:
    public_paths, refs, security_scheme_names = _build_public_paths(spec)
    public_spec = {
        key: _clone_json_compatible(value)
        for key, value in spec.items()
        if key not in {"paths", "components"}
    }
    public_spec["paths"] = public_paths

    public_components = _build_public_components(
        spec,
        refs=refs,
        security_scheme_names=security_scheme_names,
    )
    if public_components:
        public_spec["components"] = public_components

    return public_spec
