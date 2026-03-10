"""OpenAPI customization for the file API runtime."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from nova_runtime_support import (
    SDK_VISIBILITY_INTERNAL,
    apply_operation_response_refs,
    ensure_error_envelope_schema,
    ensure_error_response_component,
    install_openapi_customizer,
    mark_operation_sdk_visibility,
    prune_validation_error_schemas,
    replace_validation_error_responses,
)

OPENAPI_RESPONSE_DESCRIPTIONS = {
    "FileInvalidRequestResponse": "Canonical invalid-request response.",
    "FileUnauthorizedResponse": "Canonical unauthorized request response.",
    "FileForbiddenResponse": "Canonical forbidden request response.",
    "FileIdempotencyConflictResponse": (
        "Canonical idempotency-conflict response."
    ),
    "FileQueueUnavailableResponse": "Canonical queue unavailable response.",
    "FileIdempotencyUnavailableResponse": (
        "Canonical idempotency-unavailable response."
    ),
}
OPENAPI_OPERATION_RESPONSES = {
    "/metrics/summary": {
        "get": {
            "401": "FileUnauthorizedResponse",
            "403": "FileForbiddenResponse",
        }
    },
    "/v1/transfers/uploads/initiate": {
        "post": {
            "401": "FileUnauthorizedResponse",
            "403": "FileForbiddenResponse",
            "409": "FileIdempotencyConflictResponse",
            "422": "FileInvalidRequestResponse",
            "503": "FileIdempotencyUnavailableResponse",
        }
    },
    "/v1/transfers/uploads/sign-parts": {
        "post": {
            "401": "FileUnauthorizedResponse",
            "403": "FileForbiddenResponse",
            "422": "FileInvalidRequestResponse",
        }
    },
    "/v1/transfers/uploads/complete": {
        "post": {
            "401": "FileUnauthorizedResponse",
            "403": "FileForbiddenResponse",
            "422": "FileInvalidRequestResponse",
        }
    },
    "/v1/transfers/uploads/abort": {
        "post": {
            "401": "FileUnauthorizedResponse",
            "403": "FileForbiddenResponse",
            "422": "FileInvalidRequestResponse",
        }
    },
    "/v1/transfers/downloads/presign": {
        "post": {
            "401": "FileUnauthorizedResponse",
            "403": "FileForbiddenResponse",
            "422": "FileInvalidRequestResponse",
        }
    },
    "/v1/jobs": {
        "get": {
            "401": "FileUnauthorizedResponse",
            "403": "FileForbiddenResponse",
            "422": "FileInvalidRequestResponse",
        },
        "post": {
            "401": "FileUnauthorizedResponse",
            "403": "FileForbiddenResponse",
            "422": "FileInvalidRequestResponse",
            "503": "FileQueueUnavailableResponse",
        },
    },
    "/v1/jobs/{job_id}": {
        "get": {
            "401": "FileUnauthorizedResponse",
            "403": "FileForbiddenResponse",
            "422": "FileInvalidRequestResponse",
        }
    },
    "/v1/jobs/{job_id}/cancel": {
        "post": {
            "401": "FileUnauthorizedResponse",
            "403": "FileForbiddenResponse",
            "422": "FileInvalidRequestResponse",
        }
    },
    "/v1/jobs/{job_id}/retry": {
        "post": {
            "401": "FileUnauthorizedResponse",
            "403": "FileForbiddenResponse",
            "422": "FileInvalidRequestResponse",
        }
    },
    "/v1/jobs/{job_id}/events": {
        "get": {
            "401": "FileUnauthorizedResponse",
            "403": "FileForbiddenResponse",
            "422": "FileInvalidRequestResponse",
        }
    },
    "/v1/internal/jobs/{job_id}/result": {
        "post": {
            "403": "FileForbiddenResponse",
            "422": "FileInvalidRequestResponse",
        }
    },
}
HTTP_METHODS = {
    "delete",
    "get",
    "head",
    "options",
    "patch",
    "post",
    "trace",
}


def install_file_api_openapi_overrides(app: FastAPI) -> None:
    """
    Install OpenAPI customizations for the file API into the given FastAPI application.
    
    Applies canonical error response components and mappings, registers session and worker-token security schemes, injects a readiness 503 response, replaces validation error responses with the file API's canonical invalid-request component, assigns per-operation security requirements (including special handling for the internal job-result endpoint), marks that endpoint as internal SDK-visible, and prunes unused validation error schemas.
    
    Parameters:
        app (FastAPI): The FastAPI application to install the OpenAPI customizer on.
    """

    def customize_openapi(schema: dict[str, Any]) -> None:
        """
        Customize the given OpenAPI schema with file API-specific components, responses, security, and visibility overrides.
        
        Performs in-place modifications to ensure the standard error envelope and canonical error response components, register session and worker token security schemes, apply operation-level response references, add a 503 readiness response for /v1/health/ready, replace validation error responses with the FileInvalidRequestResponse component, assign per-operation security (using X-Worker-Token for the internal job result endpoint and sessionAuth for other authenticated operations), mark the internal job result operation as internal SDK-visible, and prune unused validation-error schemas.
        
        Parameters:
            schema (dict[str, Any]): The mutable OpenAPI schema to modify.
        """
        ensure_error_envelope_schema(schema)
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes.setdefault(
            "sessionAuth",
            {
                "type": "apiKey",
                "in": "header",
                "name": "X-Session-Id",
                "description": "Session identifier header for caller context.",
            },
        )
        security_schemes.setdefault(
            "X-Worker-Token",
            {
                "type": "apiKey",
                "in": "header",
                "name": "X-Worker-Token",
                "description": (
                    "Worker token header for trusted job-worker calls."
                ),
            },
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
        paths = schema.get("paths", {})
        if isinstance(paths, dict):
            health_ready = paths.get("/v1/health/ready", {})
            if isinstance(health_ready, dict):
                health_ready_get = health_ready.get("get")
                if isinstance(health_ready_get, dict):
                    responses = health_ready_get.setdefault("responses", {})
                    if isinstance(responses, dict):
                        responses["503"] = {
                            "description": (
                                "Service Unavailable - Readiness failed"
                            ),
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": (
                                            "#/components/schemas/"
                                            "ReadinessResponse"
                                        )
                                    }
                                }
                            },
                        }
        replace_validation_error_responses(
            schema,
            response_component_name="FileInvalidRequestResponse",
        )
        if isinstance(paths, dict):
            for path, path_item in paths.items():
                if not isinstance(path_item, dict):
                    continue
                for method, operation in path_item.items():
                    if method not in HTTP_METHODS or not isinstance(
                        operation, dict
                    ):
                        continue
                    responses = operation.get("responses")
                    if not isinstance(responses, dict):
                        continue
                    if "401" not in responses and "403" not in responses:
                        continue
                    if (
                        path == "/v1/internal/jobs/{job_id}/result"
                        and method == "post"
                    ):
                        operation["security"] = [{"X-Worker-Token": []}]
                    else:
                        operation["security"] = [{"sessionAuth": []}]
        mark_operation_sdk_visibility(
            schema,
            path="/v1/internal/jobs/{job_id}/result",
            method="post",
            visibility=SDK_VISIBILITY_INTERNAL,
        )
        prune_validation_error_schemas(schema)

    install_openapi_customizer(app, customizer=customize_openapi)
