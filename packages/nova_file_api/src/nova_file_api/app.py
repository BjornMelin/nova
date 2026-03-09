"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anyio
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from nova_runtime_support import (
    SDK_VISIBILITY_INTERNAL,
    apply_operation_response_refs,
    canonical_error_content,
    configure_structlog,
    ensure_error_response_component,
    install_openapi_customizer,
    mark_operation_sdk_visibility,
    prune_validation_error_schemas,
    replace_validation_error_responses,
    request_id_from_request,
)

from nova_file_api.config import Settings
from nova_file_api.container import AppContainer, create_container
from nova_file_api.dependencies import BLOCKING_IO_LIMITER_STATE_KEY
from nova_file_api.errors import FileTransferError, internal_error
from nova_file_api.middleware import request_context_middleware
from nova_file_api.routes import (
    ops_router,
    transfer_router,
    v1_router,
)

_HIDDEN_FIELDS = {
    "token",
    "authorization",
    "url",
    "presigned_url",
    "signature",
}
_OPENAPI_RESPONSE_DESCRIPTIONS = {
    "FileInvalidRequestResponse": "Canonical invalid-request response.",
    "FileUnauthorizedResponse": "Canonical unauthorized request response.",
    "FileForbiddenResponse": "Canonical forbidden request response.",
    "FileQueueUnavailableResponse": "Canonical queue unavailable response.",
    "FileIdempotencyUnavailableResponse": (
        "Canonical idempotency-unavailable response."
    ),
}
_OPENAPI_OPERATION_RESPONSES = {
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


def _operation_id_from_route(route: APIRoute) -> str:
    """Use the canonical route name as the stable OpenAPI operationId."""
    return route.name


def _install_openapi_overrides(app: FastAPI) -> None:
    """Apply canonical error/visibility OpenAPI overrides."""

    def customize_openapi(schema: dict[str, Any]) -> None:
        for (
            component_name,
            description,
        ) in _OPENAPI_RESPONSE_DESCRIPTIONS.items():
            ensure_error_response_component(
                schema,
                name=component_name,
                description=description,
            )
        apply_operation_response_refs(
            schema,
            response_component_names=_OPENAPI_OPERATION_RESPONSES,
        )
        replace_validation_error_responses(
            schema,
            response_component_name="FileInvalidRequestResponse",
        )
        mark_operation_sdk_visibility(
            schema,
            path="/v1/internal/jobs/{job_id}/result",
            method="post",
            visibility=SDK_VISIBILITY_INTERNAL,
        )
        prune_validation_error_schemas(schema)

    install_openapi_customizer(app, customizer=customize_openapi)


def create_app(*, container_override: AppContainer | None = None) -> FastAPI:
    """Create configured FastAPI application."""
    configure_structlog()
    settings = (
        container_override.settings
        if container_override is not None
        else Settings()
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        setattr(
            app.state,
            BLOCKING_IO_LIMITER_STATE_KEY,
            anyio.CapacityLimiter(settings.blocking_io_thread_tokens),
        )
        app.state.container = (
            container_override
            if container_override is not None
            else create_container(settings=settings)
        )
        try:
            yield
        finally:
            close_authenticator = getattr(
                app.state.container.authenticator,
                "aclose",
                None,
            )
            if callable(close_authenticator):
                await close_authenticator()

    app = FastAPI(
        title="nova-file-api",
        version=settings.app_version,
        generate_unique_id_function=_operation_id_from_route,
        lifespan=lifespan,
    )
    _install_openapi_overrides(app)

    app.middleware("http")(request_context_middleware)
    app.include_router(ops_router)
    app.include_router(transfer_router)
    app.include_router(v1_router)

    @app.exception_handler(FileTransferError)
    async def file_transfer_error_handler(
        request: Request,
        exc: FileTransferError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=canonical_error_content(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=_request_id(request=request),
            ),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=canonical_error_content(
                code="invalid_request",
                message="request validation failed",
                details={"errors": exc.errors()},
                request_id=_request_id(request=request),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        log = structlog.get_logger("errors")
        log.exception("unhandled_exception", error_type=type(exc).__name__)
        err = internal_error("unexpected internal error")
        return JSONResponse(
            status_code=err.status_code,
            content=canonical_error_content(
                code=err.code,
                message=err.message,
                details=err.details,
                request_id=_request_id(request=request),
            ),
        )

    return app


def _request_id(*, request: Request) -> str | None:
    return request_id_from_request(request=request)


def _sanitize_log_value(value: Any) -> Any:
    """Redact nested sensitive values before they reach logs."""
    if isinstance(value, dict):
        output: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in _HIDDEN_FIELDS:
                output[key] = "[REDACTED]"
            else:
                output[key] = _sanitize_log_value(item)
        return output
    if isinstance(value, list):
        return [_sanitize_log_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_log_value(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        if "x-amz-signature=" in lowered:
            return "[REDACTED]"
    return value


def _redact_sensitive_fields(
    _logger: Any,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Redact top-level and nested sensitive logging fields."""
    output: dict[str, Any] = {}
    for key, value in event_dict.items():
        if key.lower() in _HIDDEN_FIELDS:
            output[key] = "[REDACTED]"
        else:
            output[key] = _sanitize_log_value(value)
    return output
