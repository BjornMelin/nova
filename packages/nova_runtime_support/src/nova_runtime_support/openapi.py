"""Shared OpenAPI schema helpers for Nova runtime services."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast

from fastapi import FastAPI

SDK_VISIBILITY_EXTENSION = "x-nova-sdk-visibility"
SDK_VISIBILITY_INTERNAL = "internal"
_HTTP_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
)
_VALIDATION_SCHEMA_NAMES = ("HTTPValidationError", "ValidationError")

OpenApiSchemaCustomizer = Callable[[dict[str, Any]], None]


def install_openapi_customizer(
    app: FastAPI,
    *,
    customizer: OpenApiSchemaCustomizer,
) -> None:
    """Install a schema customizer on a FastAPI application.

    Args:
        app: FastAPI application whose generated OpenAPI document should be
            customized.
        customizer: Callable that mutates the generated OpenAPI schema in place.

    Returns:
        None. This mutates ``app.openapi`` so ``app.openapi()`` returns the
        customized schema on subsequent calls.

    Raises:
        TypeError: If ``app`` is not a ``FastAPI`` instance or
            ``customizer`` is not callable.
    """
    original_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema

        schema = original_openapi()
        customizer(schema)
        app.openapi_schema = schema
        return schema

    cast(Any, app).openapi = custom_openapi


def ensure_error_response_component(
    schema: dict[str, Any],
    *,
    name: str,
    description: str,
    error_schema_name: str = "ErrorEnvelope",
) -> None:
    """Ensure a reusable canonical error response component is present.

    Args:
        schema: OpenAPI document to mutate.
        name: Response component name to create or overwrite.
        description: Description text for the response component.
        error_schema_name: Target schema name for the error payload body.

    Returns:
        None. Adds or updates ``components.responses[name]``.

    Raises:
        TypeError: If ``schema`` is not a mapping type.
    """
    components = schema.setdefault("components", {})
    responses = components.setdefault("responses", {})
    responses[name] = {
        "description": description,
        "content": {
            "application/json": {
                "schema": {"$ref": f"#/components/schemas/{error_schema_name}"}
            }
        },
    }


def ensure_error_envelope_schema(
    schema: dict[str, Any],
    *,
    name: str = "ErrorEnvelope",
) -> None:
    """Ensure the canonical error envelope schema is present.

    Args:
        schema: OpenAPI document to mutate.
        name: Schema component name to create or overwrite.

    Returns:
        None. Adds or updates ``components.schemas[name]``.

    Raises:
        TypeError: If ``schema`` is not a mapping type.
    """
    components = schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    schemas.setdefault(
        name,
        {
            "type": "object",
            "title": name,
            "required": ["error"],
            "properties": {
                "error": {
                    "type": "object",
                    "required": ["code", "message"],
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "details": {"type": "object"},
                        "request_id": {
                            "type": ["string", "null"],
                        },
                    },
                    "additionalProperties": True,
                }
            },
            "additionalProperties": False,
        },
    )


def replace_validation_error_responses(
    schema: dict[str, Any],
    *,
    response_component_name: str,
) -> None:
    """Replace FastAPI default 422 validation responses with canonical refs.

    Args:
        schema: OpenAPI document to mutate.
        response_component_name: Component key under
            ``components.responses`` that should be used for 422 responses.

    Returns:
        None. For each operation with a 422 response, the response entry is
        replaced with ``#/components/responses/{response_component_name}``.

    Raises:
        TypeError: If ``schema`` is not a mapping type.
    """
    response_ref = {"$ref": f"#/components/responses/{response_component_name}"}
    paths = schema.get("paths", {})
    if not isinstance(paths, dict):
        return
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            responses = operation.get("responses")
            if not isinstance(responses, dict):
                continue
            response_422 = responses.get("422")
            if isinstance(response_422, dict):
                responses["422"] = response_ref


def mark_operation_sdk_visibility(
    schema: dict[str, Any],
    *,
    path: str,
    method: str,
    visibility: str,
) -> None:
    """Mark one operation with an SDK visibility extension.

    Args:
        schema: OpenAPI document to mutate.
        path: Path key that contains the target operation.
        method: HTTP method for the target operation, case-insensitive.
        visibility: Visibility value written to ``x-nova-sdk-visibility``.

    Returns:
        None. When the operation exists, writes the visibility marker on it.

    Raises:
        TypeError: If ``schema`` is not a mapping type.
    """
    paths = schema.get("paths", {})
    if not isinstance(paths, dict):
        return
    path_item = paths.get(path)
    if not isinstance(path_item, dict):
        return
    operation = path_item.get(method.lower())
    if isinstance(operation, dict):
        operation[SDK_VISIBILITY_EXTENSION] = visibility


def prune_validation_error_schemas(schema: dict[str, Any]) -> None:
    """Remove unused FastAPI validation schema components.

    Args:
        schema: OpenAPI document to mutate.

    Returns:
        None. Removes ``HTTPValidationError`` and ``ValidationError`` from
        ``components.schemas`` when they are no longer referenced.

    Raises:
        TypeError: If ``schema`` is not a mapping type.
    """
    components = schema.get("components")
    if not isinstance(components, dict):
        return
    schemas = components.get("schemas")
    if not isinstance(schemas, dict):
        return
    schema_refs = _collect_schema_refs(schema=schema)
    for schema_name in _VALIDATION_SCHEMA_NAMES:
        schema_ref = f"#/components/schemas/{schema_name}"
        if schema_ref in schema_refs:
            continue
        schemas.pop(schema_name, None)


def _collect_schema_refs(schema: dict[str, Any]) -> set[str]:
    refs: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            ref_value = node.get("$ref")
            if isinstance(ref_value, str):
                refs.add(ref_value)
            for value in node.values():
                walk(value)
            return
        if isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    return refs


def apply_operation_response_refs(
    schema: dict[str, Any],
    *,
    response_component_names: Mapping[str, Mapping[str, Mapping[str, str]]],
) -> None:
    """Apply reusable response-component refs to concrete operations.

    Args:
        schema: OpenAPI root document to mutate in place.
        response_component_names: Mapping of
            path -> method -> status -> component.

    Returns:
        None. This mutates ``schema`` in-place by replacing operation
        responses with ``$ref`` objects.
    """
    paths = schema.get("paths", {})
    if not isinstance(paths, dict):
        return
    for path, method_map in response_component_names.items():
        path_item = paths.get(path)
        if not isinstance(path_item, dict):
            continue
        for method, responses in method_map.items():
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            operation_responses = operation.setdefault("responses", {})
            if not isinstance(operation_responses, dict):
                continue
            for status_code, component_name in responses.items():
                operation_responses[status_code] = {
                    "$ref": f"#/components/responses/{component_name}"
                }
