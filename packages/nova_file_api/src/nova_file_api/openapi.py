"""Public OpenAPI customization seam for the file API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI

_HTTP_VALIDATION_ERROR_DETAIL_MAX_ITEMS = 256
_HTTP_VALIDATION_ERROR_LOC_MAX_ITEMS = 32
_HTTP_VALIDATION_ERROR_DESCRIPTION = (
    "Validation error envelope returned for invalid request payloads."
)
_VALIDATION_ERROR_DESCRIPTION = (
    "One request-validation issue with location, message, and error type."
)
_HTTP_VALIDATION_ERROR_DETAIL_DESCRIPTION = (
    "Collection of request-validation issues returned by FastAPI."
)
_VALIDATION_ERROR_PROPERTY_DESCRIPTIONS = {
    "ctx": "Optional structured context attached to the validation issue.",
    "input": (
        "Original input value that failed validation when FastAPI exposes it."
    ),
    "loc": "Ordered location path that identifies the invalid request field.",
    "msg": "Human-readable validation message.",
    "type": "Machine-readable validation error type identifier.",
}


def patch_http_validation_error_schema(schema: dict[str, Any]) -> None:
    """Bound and document FastAPI validation error payloads."""
    schemas = schema.get("components", {}).get("schemas", {})
    if not isinstance(schemas, dict):
        return
    http_validation_error = schemas.get("HTTPValidationError", {})
    validation_error = schemas.get("ValidationError", {})

    if isinstance(http_validation_error, dict):
        http_validation_error.setdefault(
            "description",
            _HTTP_VALIDATION_ERROR_DESCRIPTION,
        )
    if isinstance(validation_error, dict):
        validation_error.setdefault(
            "description",
            _VALIDATION_ERROR_DESCRIPTION,
        )

    detail = (
        http_validation_error.get("properties", {}).get("detail")
        if isinstance(http_validation_error, dict)
        else None
    )
    if isinstance(detail, dict) and detail.get("type") == "array":
        detail.setdefault(
            "description",
            _HTTP_VALIDATION_ERROR_DETAIL_DESCRIPTION,
        )
        detail["maxItems"] = _HTTP_VALIDATION_ERROR_DETAIL_MAX_ITEMS
    validation_error_properties = (
        validation_error.get("properties", {})
        if isinstance(validation_error, dict)
        else None
    )
    if isinstance(validation_error_properties, dict):
        for (
            property_name,
            property_description,
        ) in _VALIDATION_ERROR_PROPERTY_DESCRIPTIONS.items():
            property_schema = validation_error_properties.get(property_name)
            if isinstance(property_schema, dict):
                property_schema.setdefault(
                    "description",
                    property_description,
                )
    loc = (
        validation_error.get("properties", {}).get("loc")
        if isinstance(validation_error, dict)
        else None
    )
    if isinstance(loc, dict) and loc.get("type") == "array":
        loc["maxItems"] = _HTTP_VALIDATION_ERROR_LOC_MAX_ITEMS


def assign_openapi_override(
    *,
    app: Any,
    custom_openapi: Callable[[], dict[str, Any]],
) -> None:
    """Assign FastAPI's documented OpenAPI override hook."""
    app.openapi = custom_openapi


def install_openapi_override(*, app: FastAPI) -> None:
    """Install the documented OpenAPI override on one app instance."""
    original_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        schema = app.openapi_schema
        if schema is not None:
            return schema
        schema = original_openapi()
        patch_http_validation_error_schema(schema)
        app.openapi_schema = schema
        return schema

    assign_openapi_override(app=app, custom_openapi=custom_openapi)


__all__ = [
    "assign_openapi_override",
    "install_openapi_override",
    "patch_http_validation_error_schema",
]
