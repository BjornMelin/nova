"""FastAPI application factory for nova-auth-api."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from nova_auth_api.config import Settings
from nova_auth_api.errors import AuthApiError, internal_error
from nova_auth_api.models import (
    ErrorBody,
    ErrorEnvelope,
    HealthResponse,
    TokenIntrospectRequest,
    TokenIntrospectResponse,
    TokenVerifyRequest,
    TokenVerifyResponse,
)
from nova_auth_api.service import TokenVerificationService


def create_app(
    *,
    settings_override: Settings | None = None,
    service_override: TokenVerificationService | None = None,
) -> FastAPI:
    """Create configured FastAPI application."""
    _configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings = settings_override or Settings()
        app.state.settings = settings
        app.state.auth_service = service_override or TokenVerificationService(
            settings=settings
        )
        yield

    app = FastAPI(
        title="nova-auth-api",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.middleware("http")(request_context_middleware)

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        """Return liveness status."""
        return HealthResponse(ok=True)

    @app.post("/v1/token/verify", response_model=TokenVerifyResponse)
    async def verify_token(
        payload: TokenVerifyRequest,
        request: Request,
    ) -> TokenVerifyResponse:
        """Verify access token and return principal plus claims."""
        service = _service(request=request)
        return await service.verify(payload)

    @app.post(
        "/v1/token/introspect",
        response_model=TokenIntrospectResponse,
    )
    async def introspect_token(
        payload: TokenIntrospectRequest,
        request: Request,
    ) -> TokenIntrospectResponse:
        """Introspect token and return active status plus claim details."""
        service = _service(request=request)
        return await service.introspect(payload)

    @app.exception_handler(AuthApiError)
    async def auth_error_handler(
        request: Request,
        exc: AuthApiError,
    ) -> JSONResponse:
        """Convert domain auth errors into canonical HTTP responses."""
        payload = ErrorEnvelope(
            error=ErrorBody(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=_request_id(request=request),
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(),
            headers=exc.headers or None,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Convert unexpected exceptions into canonical error envelopes."""
        log = structlog.get_logger("errors")
        log.exception("unhandled_exception", error_type=type(exc).__name__)
        err = internal_error("unexpected internal error")
        payload = ErrorEnvelope(
            error=ErrorBody(
                code=err.code,
                message=err.message,
                details=err.details,
                request_id=_request_id(request=request),
            )
        )
        return JSONResponse(
            status_code=err.status_code,
            content=payload.model_dump(),
        )

    return app


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("X-Request-Id") or uuid4().hex
    request.state.request_id = request_id
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response: Response | None = None
    try:
        response = await call_next(request)
        return response
    finally:
        if response is not None:
            response.headers["X-Request-Id"] = request_id
        structlog.contextvars.unbind_contextvars("request_id")


def _service(*, request: Request) -> TokenVerificationService:
    value = getattr(request.app.state, "auth_service", None)
    if isinstance(value, TokenVerificationService):
        return value
    raise RuntimeError("auth service not initialized")


def _request_id(*, request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and value:
        return value
    value = request.headers.get("X-Request-Id")
    if isinstance(value, str) and value:
        return value
    return None


def _configure_logging() -> None:
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


def _redact_sensitive_fields(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Redact sensitive token fields before emitting structured logs."""
    output: dict[str, Any] = {}
    hidden_fields = {"token", "authorization", "access_token"}
    for key, value in event_dict.items():
        if key.lower() in hidden_fields:
            output[key] = "[REDACTED]"
        else:
            output[key] = value
    return output
