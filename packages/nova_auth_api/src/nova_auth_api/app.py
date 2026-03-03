"""FastAPI application factory for nova-auth-api."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping
from contextlib import asynccontextmanager
from json import JSONDecodeError
from typing import Any
from urllib.parse import parse_qs
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
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
from nova_auth_api.service import (
    TokenVerificationService,
    _set_verifier_thread_tokens,
)

_AUTH_SERVICE_NOT_INITIALIZED = "auth service not initialized"
_LOGGING_CONFIGURED = False
_FORM_MEDIA_TYPE = "application/x-www-form-urlencoded"
_JSON_MEDIA_TYPE = "application/json"
_INTROSPECT_REQUEST_BODY: dict[str, Any] = {
    "required": True,
    "content": {
        _JSON_MEDIA_TYPE: {
            "schema": {
                "$ref": "#/components/schemas/TokenIntrospectRequest",
            }
        },
        _FORM_MEDIA_TYPE: {
            "schema": {
                "type": "object",
                "required": ["token"],
                "properties": {
                    "token": {"type": "string", "minLength": 1},
                    "token_type_hint": {"type": "string"},
                    "required_scopes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "required_permissions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            }
        },
    },
}


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
        _set_verifier_thread_tokens(settings.oidc_verifier_thread_tokens)
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

    @app.get("/v1/health/live", response_model=HealthResponse)
    async def health_live(request: Request) -> HealthResponse:
        """Return liveness status."""
        request_id = _request_id(request=request) or uuid4().hex
        return HealthResponse(
            status="ok",
            service="nova-auth-api",
            request_id=request_id,
        )

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
        openapi_extra={"requestBody": _INTROSPECT_REQUEST_BODY},
    )
    async def introspect_token(
        request: Request,
    ) -> TokenIntrospectResponse:
        """Introspect token and return active status plus claim details."""
        payload = await _parse_introspect_payload(request=request)
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
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        payload = ErrorEnvelope(
            error=ErrorBody(
                code="invalid_request",
                message="request validation failed",
                details={"errors": exc.errors()},
                request_id=_request_id(request=request),
            )
        )
        return JSONResponse(
            status_code=422,
            content=payload.model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Convert unexpected exceptions into canonical error envelopes."""
        log = structlog.get_logger("errors")
        log.exception(
            "unhandled_exception",
            error_type=type(exc).__name__,
            request_id=_request_id(request=request),
        )
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
    """Inject request ID into context and response headers."""
    request_id = request.headers.get("X-Request-Id") or uuid4().hex
    request.state.request_id = request_id
    structlog.contextvars.bind_contextvars(request_id=request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
    finally:
        structlog.contextvars.unbind_contextvars("request_id")


def _service(*, request: Request) -> TokenVerificationService:
    value = getattr(request.app.state, "auth_service", None)
    if isinstance(value, TokenVerificationService):
        return value
    raise RuntimeError(_AUTH_SERVICE_NOT_INITIALIZED)


def _request_id(*, request: Request) -> str | None:
    """Extract request ID from request state or headers."""
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and value:
        return value
    value = request.headers.get("X-Request-Id")
    if isinstance(value, str) and value:
        return value
    return None


async def _parse_introspect_payload(
    *,
    request: Request,
) -> TokenIntrospectRequest:
    media_type = _request_media_type(request=request)
    if media_type == _FORM_MEDIA_TYPE:
        raw_payload = _parse_form_payload(body=await request.body())
    else:
        try:
            raw_payload = await request.json()
        except (JSONDecodeError, UnicodeDecodeError) as exc:
            raise RequestValidationError(
                [
                    {
                        "type": "json_invalid",
                        "loc": ("body",),
                        "msg": "JSON decode error",
                        "input": None,
                    }
                ]
            ) from exc

    if not isinstance(raw_payload, dict):
        raise RequestValidationError(
            [
                {
                    "type": "model_attributes_type",
                    "loc": ("body",),
                    "msg": "Input should be a valid dictionary",
                    "input": raw_payload,
                }
            ]
        )

    normalized_payload = _normalize_introspect_payload(raw_payload=raw_payload)
    try:
        return TokenIntrospectRequest.model_validate(normalized_payload)
    except ValidationError as exc:
        raise RequestValidationError(
            _with_body_loc(errors=exc.errors())
        ) from exc


def _request_media_type(*, request: Request) -> str:
    value = request.headers.get("content-type")
    if not isinstance(value, str):
        return _JSON_MEDIA_TYPE
    return value.split(";", 1)[0].strip().lower()


def _parse_form_payload(*, body: bytes) -> dict[str, Any]:
    try:
        decoded_body = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RequestValidationError(
            [
                {
                    "type": "unicode_decode_error",
                    "loc": ("body",),
                    "msg": "request body must be UTF-8 encoded",
                    "input": None,
                }
            ]
        ) from exc

    parsed = parse_qs(decoded_body, keep_blank_values=True)
    payload: dict[str, Any] = {}
    for key, values in parsed.items():
        if key in {"required_scopes", "required_permissions"}:
            payload[key] = values
            continue
        payload[key] = values[-1] if values else ""
    return payload


def _normalize_introspect_payload(
    *,
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    payload = dict(raw_payload)
    token_value = payload.get("token")
    if "access_token" not in payload and token_value is not None:
        payload["access_token"] = token_value
    payload.pop("token", None)
    payload.pop("token_type_hint", None)
    return payload


def _with_body_loc(*, errors: list[Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for error in errors:
        if not isinstance(error, dict):
            continue
        output.append(
            {
                **error,
                "loc": ("body", *list(error.get("loc", ()))),
            }
        )
    return output


def _configure_logging() -> None:
    """Configure structured logging."""
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
    """Redact sensitive token fields before emitting structured logs."""
    hidden_fields = {"token", "authorization", "access_token"}

    def _sanitize(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    "[REDACTED]"
                    if key.lower() in hidden_fields
                    else _sanitize(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list | tuple):
            return [_sanitize(item) for item in value]
        return value

    return {
        key: "[REDACTED]" if key.lower() in hidden_fields else _sanitize(value)
        for key, value in event_dict.items()
    }
