"""Shared ASGI/FastAPI request-context and canonical error-envelope helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Protocol, TypeVar
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request as StarletteRequest
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ExceptionAdapter = Callable[[Exception], "CanonicalErrorSpec"]
ValidationDetailsAdapter = Callable[[RequestValidationError], Mapping[str, Any]]
DomainErrorT = TypeVar("DomainErrorT", bound=Exception)

_REQUEST_ID_HEADER = "X-Request-Id"


def _headers_include_request_id(headers: Mapping[str, str]) -> bool:
    want = _REQUEST_ID_HEADER.lower()
    return any(key.lower() == want for key in headers)


@dataclass(slots=True)
class CanonicalErrorSpec:
    """Describe one canonical Nova error response."""

    status_code: int
    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)


class CanonicalErrorLike(Protocol):
    """Structural contract for domain errors already shaped for the envelope."""

    status_code: int
    code: str
    message: str


class RequestContextASGIMiddleware:
    """Attach request context and request-id headers without touching bodies."""

    def __init__(self, app: ASGIApp) -> None:
        """Store the downstream ASGI application."""
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Bind request context, inject response headers, and log completion."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = StarletteRequest(scope)
        request_id = _request_id_from_headers(request.headers)
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        logger = structlog.get_logger("http")
        started = perf_counter()
        method = request.method
        path = request.url.path
        status_code: int | None = None
        request_failed = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                MutableHeaders(scope=message)[_REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            request_failed = True
            latency_ms = (perf_counter() - started) * 1000.0
            logger.exception(
                "request_completed",
                method=method,
                path=path,
                status_code=status_code or 500,
                outcome="error",
                latency_ms=round(latency_ms, 3),
            )
            raise
        finally:
            if (not request_failed) and status_code is not None:
                latency_ms = (perf_counter() - started) * 1000.0
                logger.info(
                    "request_completed",
                    method=method,
                    path=path,
                    status_code=status_code,
                    outcome="ok" if status_code < 400 else "error",
                    latency_ms=round(latency_ms, 3),
                )
            structlog.contextvars.clear_contextvars()


def register_fastapi_exception_handlers(
    app: FastAPI,
    *,
    domain_error_type: type[DomainErrorT],
    adapt_domain_error: Callable[[DomainErrorT], CanonicalErrorSpec],
    validation_error_details: ValidationDetailsAdapter,
    adapt_unhandled_error: ExceptionAdapter,
    extra_exception_adapters: (
        Mapping[type[Exception], ExceptionAdapter] | None
    ) = None,
    logger_name: str = "errors",
) -> None:
    """Register canonical FastAPI exception handlers for one application."""

    @app.exception_handler(domain_error_type)
    async def domain_error_handler(
        request: Request,
        exc: DomainErrorT,
    ) -> JSONResponse:
        spec = adapt_domain_error(exc)
        return _json_error_response(request=request, spec=spec)

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        details = dict(validation_error_details(exc))
        spec = CanonicalErrorSpec(
            status_code=422,
            code="invalid_request",
            message="request validation failed",
            details=details,
        )
        return _json_error_response(request=request, spec=spec)

    for exception_type, adapter in (extra_exception_adapters or {}).items():
        _register_extra_exception_handler(
            app=app,
            exception_type=exception_type,
            adapter=adapter,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        request_id = request_id_from_request(request=request)
        structlog.get_logger(logger_name).exception(
            "unhandled_exception",
            error_type=type(exc).__name__,
            request_id=request_id,
        )
        return _json_error_response(
            request=request,
            spec=adapt_unhandled_error(exc),
        )


def canonical_error_spec_from_error(
    exc: CanonicalErrorLike,
) -> CanonicalErrorSpec:
    """Build a canonical transport spec from a domain error object."""
    details = getattr(exc, "details", {})
    headers = dict(getattr(exc, "headers", {}))
    if int(exc.status_code) == 401 and "WWW-Authenticate" not in headers:
        headers["WWW-Authenticate"] = (
            'Bearer error="invalid_token", '
            'error_description="missing bearer token"'
        )
    return CanonicalErrorSpec(
        status_code=int(exc.status_code),
        code=exc.code,
        message=exc.message,
        details=details,
        headers=headers,
    )


def _register_extra_exception_handler(
    *,
    app: FastAPI,
    exception_type: type[Exception],
    adapter: ExceptionAdapter,
) -> None:
    """Register one additional FastAPI exception adapter."""

    @app.exception_handler(exception_type)
    async def extra_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        return _json_error_response(request=request, spec=adapter(exc))


def _json_error_response(
    *,
    request: Request,
    spec: CanonicalErrorSpec,
) -> JSONResponse:
    """Serialize one canonical error response for the current request."""
    request_id = request_id_from_request(request=request)
    headers = dict(spec.headers)
    if request_id and not _headers_include_request_id(headers):
        headers[_REQUEST_ID_HEADER] = request_id
    return JSONResponse(
        status_code=spec.status_code,
        content=canonical_error_content(
            code=spec.code,
            message=spec.message,
            details=spec.details,
            request_id=request_id,
        ),
        headers=headers,
    )


def request_id_from_request(*, request: Request) -> str | None:
    """Read the normalized request identifier from request state or headers.

    Args:
        request: Incoming request object with state and headers.

    Returns:
        str | None: Normalized request id when available, otherwise ``None``.
    """
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and value:
        return value
    value = request.headers.get(_REQUEST_ID_HEADER)
    if isinstance(value, str) and value:
        return value
    return None


def canonical_error_content(
    *,
    code: str,
    message: str,
    details: Mapping[str, Any] | None = None,
    request_id: str | None,
) -> dict[str, Any]:
    """Build the canonical Nova error envelope payload as a JSON-ready dict.

    Args:
        code: Canonical machine-readable error code.
        message: Human-readable error message.
        details: Optional structured detail payload.
        request_id: Request identifier to include in the envelope.

    Returns:
        dict[str, Any]: Canonical error payload with top-level ``error`` key.
    """
    return {
        "error": {
            "code": code,
            "message": message,
            "details": dict(details or {}),
            "request_id": request_id,
        }
    }


def _request_id_from_headers(headers: Headers) -> str:
    """Return the caller request ID or mint a new identifier."""
    request_id = headers.get(_REQUEST_ID_HEADER)
    if isinstance(request_id, str) and request_id:
        return request_id
    return uuid4().hex
