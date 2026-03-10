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
    """Install auth-service OpenAPI customizations on the application."""

    def customize_openapi(schema: dict[str, Any]) -> None:
        """
        Apply auth-specific components, responses, and path-level adjustments to an OpenAPI schema.
        
        Mutates the provided OpenAPI schema in-place to ensure token introspection request schemas exist, register a bearerAuth security scheme, add a canonical error envelope and standardized error response components, map operation responses to those canonical components, replace validation error responses with the canonical invalid-request response, annotate introspection POST operations with an x-auth-not-required hint and attach the introspection request body where required, and prune unused validation-error schemas.
        
        Parameters:
            schema (dict[str, Any]): The OpenAPI schema object to modify in-place.
        """
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