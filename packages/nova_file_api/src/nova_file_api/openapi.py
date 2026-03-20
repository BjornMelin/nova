"""OpenAPI customization for the file API runtime."""

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

OPENAPI_RESPONSE_DESCRIPTIONS = {
    "FileInvalidRequestResponse": "Canonical invalid-request response.",
    "FileUnauthorizedResponse": "Canonical unauthorized request response.",
    "FileForbiddenResponse": "Canonical forbidden request response.",
    "FileIdempotencyConflictResponse": (
        "Canonical idempotency-conflict response."
    ),
    "FileMutationUnavailableResponse": (
        "Canonical mutation dependency-unavailable response."
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
    "/v1/transfers/uploads/introspect": {
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
            "409": "FileIdempotencyConflictResponse",
            "422": "FileInvalidRequestResponse",
            "503": "FileMutationUnavailableResponse",
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
}


def install_file_api_openapi_overrides(app: FastAPI) -> None:
    """Apply canonical error/visibility OpenAPI overrides."""

    def customize_openapi(schema: dict[str, Any]) -> None:
        ensure_error_envelope_schema(schema)
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
        prune_validation_error_schemas(schema)

    install_openapi_customizer(app, customizer=customize_openapi)
