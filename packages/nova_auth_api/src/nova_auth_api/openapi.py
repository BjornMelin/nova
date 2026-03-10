"""OpenAPI customization for nova-auth-api."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from nova_runtime_support import (
    apply_operation_response_refs,
    ensure_error_envelope_schema,
    ensure_error_response_component,
    install_openapi_customizer,
    prune_validation_error_schemas,
    replace_validation_error_responses,
)

from nova_auth_api.request_parsing import (
    INTROSPECT_REQUEST_BODY,
    TOKEN_INTROSPECT_FORM_REQUEST_SCHEMA,
    TOKEN_INTROSPECT_REQUEST_SCHEMA,
)

INTROSPECTION_AUTH_PATHS = {
    "/v1/token/verify",
    "/v1/token/introspect",
}
OPENAPI_RESPONSE_DESCRIPTIONS = {
    "AuthInvalidRequestResponse": "Canonical invalid-request response.",
    "AuthUnauthorizedResponse": "Canonical unauthorized token response.",
    "AuthForbiddenResponse": "Canonical insufficient-scope response.",
    "AuthServiceUnavailableResponse": "Canonical service unavailable response.",
}
OPENAPI_OPERATION_RESPONSES = {
    "/v1/health/ready": {
        "get": {"503": "AuthServiceUnavailableResponse"},
    },
    "/v1/token/verify": {
        "post": {
            "401": "AuthUnauthorizedResponse",
            "403": "AuthForbiddenResponse",
            "503": "AuthServiceUnavailableResponse",
            "422": "AuthInvalidRequestResponse",
        }
    },
    "/v1/token/introspect": {
        "post": {
            "401": "AuthUnauthorizedResponse",
            "403": "AuthForbiddenResponse",
            "503": "AuthServiceUnavailableResponse",
            "422": "AuthInvalidRequestResponse",
        }
    },
}


def install_auth_openapi(app: FastAPI) -> None:
    """Install auth-service OpenAPI customizations on the application.

    Args:
        app: FastAPI application instance to customize.

    Returns:
        None
    """

    def customize_openapi(schema: dict[str, Any]) -> None:
        components = schema.setdefault("components", {})
        schemas = components.setdefault("schemas", {})
        schemas.setdefault(
            "TokenIntrospectRequest",
            TOKEN_INTROSPECT_REQUEST_SCHEMA,
        )
        schemas.setdefault(
            "TokenIntrospectFormRequest",
            TOKEN_INTROSPECT_FORM_REQUEST_SCHEMA,
        )
        ensure_error_envelope_schema(schema)
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes.setdefault(
            "bearerAuth",
            {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
        )
        for (
            component_name,
            description,
        ) in OPENAPI_RESPONSE_DESCRIPTIONS.items():
            ensure_error_response_component(
                schema,
                name=component_name,
                description=description,
            )
        apply_operation_response_refs(
            schema,
            response_component_names=OPENAPI_OPERATION_RESPONSES,
        )
        replace_validation_error_responses(
            schema,
            response_component_name="AuthInvalidRequestResponse",
        )
        paths = schema.get("paths", {})
        if isinstance(paths, dict):
            for path in INTROSPECTION_AUTH_PATHS:
                operation = paths.get(path, {}).get("post")
                if isinstance(operation, dict):
                    operation["x-auth-not-required"] = (
                        "Auth-validation endpoint; "
                        "bearerAuth is intentionally not required."
                    )
                    if path == "/v1/token/introspect":
                        operation["requestBody"] = INTROSPECT_REQUEST_BODY
        prune_validation_error_schemas(schema)

    install_openapi_customizer(app, customizer=customize_openapi)
