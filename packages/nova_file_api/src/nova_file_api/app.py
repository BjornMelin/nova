"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, MutableMapping
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from nova_file_api.api import jobs_router, ops_router, transfer_router
from nova_file_api.auth import _set_verifier_thread_tokens
from nova_file_api.config import Settings
from nova_file_api.container import AppContainer, create_container
from nova_file_api.errors import FileTransferError, internal_error
from nova_file_api.middleware import request_context_middleware
from nova_file_api.models import ErrorBody, ErrorEnvelope

_LOGGING_CONFIGURED = False
_HIDDEN_FIELDS = {
    "token",
    "authorization",
    "url",
    "presigned_url",
    "signature",
}


def create_app(*, container_override: AppContainer | None = None) -> FastAPI:
    """Create configured FastAPI application."""
    _configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings = Settings()
        _set_verifier_thread_tokens(settings.oidc_verifier_thread_tokens)
        app.state.settings = settings
        app.state.container = (
            container_override
            if container_override is not None
            else create_container(settings=settings)
        )
        yield

    app = FastAPI(
        title="nova-file-api",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.middleware("http")(request_context_middleware)
    app.include_router(transfer_router)
    app.include_router(jobs_router)
    app.include_router(ops_router)

    @app.exception_handler(FileTransferError)
    async def file_transfer_error_handler(
        request: Request,
        exc: FileTransferError,
    ) -> JSONResponse:
        request_id = _request_id(request=request)
        payload = ErrorEnvelope(
            error=ErrorBody(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=request_id,
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        log = structlog.get_logger("errors")
        log.exception("unhandled_exception", error_type=type(exc).__name__)
        err = internal_error("unexpected internal error")
        request_id = _request_id(request=request)
        payload = ErrorEnvelope(
            error=ErrorBody(
                code=err.code,
                message=err.message,
                details=err.details,
                request_id=request_id,
            )
        )
        return JSONResponse(
            status_code=err.status_code,
            content=payload.model_dump(),
        )

    return app


def _request_id(*, request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str):
        return value
    return None


def _configure_logging() -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _redact_sensitive_fields,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _LOGGING_CONFIGURED = True


def _redact_sensitive_fields(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Redact sensitive fields before emitting structured logs."""
    output: dict[str, Any] = {}
    for key, value in event_dict.items():
        if key.lower() in _HIDDEN_FIELDS:
            output[key] = "[REDACTED]"
        else:
            output[key] = _sanitize_log_value(value)
    return output


def _sanitize_log_value(value: object) -> object:
    """Recursively sanitize nested structured log values."""
    if isinstance(value, str):
        if "X-Amz-Signature=" in value or "X-Amz-Credential=" in value:
            return "[REDACTED]"
        return value
    if isinstance(value, dict):
        nested: dict[str, object] = {}
        for key, item in value.items():
            if key.lower() in _HIDDEN_FIELDS:
                nested[key] = "[REDACTED]"
            else:
                nested[key] = _sanitize_log_value(item)
        return nested
    if isinstance(value, list):
        return [_sanitize_log_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_log_value(item) for item in value)
    return value
