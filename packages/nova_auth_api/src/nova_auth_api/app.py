"""FastAPI application factory for nova-auth-api."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from json import JSONDecodeError
from typing import Annotated, Any
from urllib.parse import parse_qs

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from nova_runtime_support import (
    apply_operation_response_refs,
    bind_request_id,
    canonical_error_content,
    configure_structlog,
    ensure_error_response_component,
    finalize_request_id,
    install_openapi_customizer,
    prune_validation_error_schemas,
    replace_validation_error_responses,
    request_id_from_request,
    unbind_request_id,
)
from pydantic import ValidationError
from starlette.responses import Response

from nova_auth_api.config import Settings
from nova_auth_api.dependencies import (
    TokenVerificationServiceDep,
)
from nova_auth_api.errors import (
    AuthApiError,
    internal_error,
    service_unavailable,
)
from nova_auth_api.models import (
    HealthResponse,
    TokenIntrospectRequest,
    TokenIntrospectResponse,
    TokenVerifyRequest,
    TokenVerifyResponse,
)
from nova_auth_api.service import TokenVerificationService

_FORM_MEDIA_TYPE = "application/x-www-form-urlencoded"
_JSON_MEDIA_TYPE = "application/json"
_TOKEN_INTROSPECT_JSON_REQUEST_SCHEMA_REF = {
    "$ref": "#/components/schemas/TokenIntrospectRequest"
}
_TOKEN_INTROSPECT_FORM_REQUEST_SCHEMA_REF = {
    "$ref": "#/components/schemas/TokenIntrospectFormRequest"
}
_INTROSPECT_REQUEST_BODY: dict[str, Any] = {
    "required": True,
    "content": {
        _JSON_MEDIA_TYPE: {"schema": _TOKEN_INTROSPECT_JSON_REQUEST_SCHEMA_REF},
        _FORM_MEDIA_TYPE: {"schema": _TOKEN_INTROSPECT_FORM_REQUEST_SCHEMA_REF},
    },
}
_TOKEN_INTROSPECT_REQUEST_SCHEMA = TokenIntrospectRequest.model_json_schema(
    ref_template="#/components/schemas/{model}"
)
_TOKEN_INTROSPECT_FORM_REQUEST_SCHEMA = {
    **_TOKEN_INTROSPECT_REQUEST_SCHEMA,
    "title": "TokenIntrospectFormRequest",
}
_OPENAPI_RESPONSE_DESCRIPTIONS = {
    "AuthInvalidRequestResponse": "Canonical invalid-request response.",
    "AuthUnauthorizedResponse": "Canonical unauthorized token response.",
    "AuthForbiddenResponse": "Canonical insufficient-scope response.",
    "AuthServiceUnavailableResponse": "Canonical service unavailable response.",
}
_OPENAPI_OPERATION_RESPONSES = {
    "/v1/health/ready": {
        "get": {"503": "AuthServiceUnavailableResponse"},
    },
    "/v1/token/verify": {
        "post": {
            "401": "AuthUnauthorizedResponse",
            "403": "AuthForbiddenResponse",
            "422": "AuthInvalidRequestResponse",
        }
    },
    "/v1/token/introspect": {
        "post": {
            "401": "AuthUnauthorizedResponse",
            "403": "AuthForbiddenResponse",
            "422": "AuthInvalidRequestResponse",
        }
    },
}


def _operation_id_from_route(route: APIRoute) -> str:
    """Use the canonical route name as the stable OpenAPI operationId."""
    return route.name


def _install_openapi_overrides(app: FastAPI) -> None:
    """Inject schema components required by custom OpenAPI request bodies."""

    def customize_openapi(schema: dict[str, Any]) -> None:
        components = schema.setdefault("components", {})
        schemas = components.setdefault("schemas", {})
        schemas.setdefault(
            "TokenIntrospectRequest",
            _TOKEN_INTROSPECT_REQUEST_SCHEMA,
        )
        schemas.setdefault(
            "TokenIntrospectFormRequest",
            _TOKEN_INTROSPECT_FORM_REQUEST_SCHEMA,
        )
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
            response_component_name="AuthInvalidRequestResponse",
        )
        prune_validation_error_schemas(schema)

    install_openapi_customizer(app, customizer=customize_openapi)


def create_app(
    *,
    settings_override: Settings | None = None,
    service_override: TokenVerificationService | None = None,
) -> FastAPI:
    """Create configured FastAPI application."""
    configure_structlog()
    settings = settings_override or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.auth_service = service_override or TokenVerificationService(
            settings=settings
        )
        yield

    app = FastAPI(
        title="nova-auth-api",
        version=settings.app_version,
        generate_unique_id_function=_operation_id_from_route,
        lifespan=lifespan,
    )
    _install_openapi_overrides(app)
    app.middleware("http")(request_context_middleware)

    @app.get(
        "/v1/health/live",
        response_model=HealthResponse,
        tags=["health"],
    )
    async def health_live(request: Request) -> HealthResponse:
        """Return liveness status."""
        request_id = _request_id(request=request) or bind_request_id(request)
        return HealthResponse(
            status="ok",
            service="nova-auth-api",
            request_id=request_id,
        )

    @app.get(
        "/v1/health/ready",
        response_model=HealthResponse,
        tags=["health"],
    )
    async def health_ready(
        request: Request,
        service: TokenVerificationServiceDep,
    ) -> HealthResponse:
        """Return readiness status for token verification."""
        request_id = _request_id(request=request) or bind_request_id(request)
        if not service.is_ready():
            raise service_unavailable("auth verifier unavailable")
        return HealthResponse(
            status="ok",
            service="nova-auth-api",
            request_id=request_id,
        )

    @app.post(
        "/v1/token/verify",
        response_model=TokenVerifyResponse,
        tags=["token"],
    )
    async def verify_token(
        payload: TokenVerifyRequest,
        service: TokenVerificationServiceDep,
    ) -> TokenVerifyResponse:
        """Verify access token and return principal plus claims."""
        return await service.verify(payload)

    @app.post(
        "/v1/token/introspect",
        response_model=TokenIntrospectResponse,
        tags=["token"],
        openapi_extra={"requestBody": _INTROSPECT_REQUEST_BODY},
    )
    async def introspect_token(
        payload: Annotated[
            TokenIntrospectRequest, Depends(_parse_introspect_request)
        ],
        service: TokenVerificationServiceDep,
    ) -> TokenIntrospectResponse:
        """Introspect token and return active status plus claim details."""
        return await service.introspect(payload)

    @app.exception_handler(AuthApiError)
    async def auth_error_handler(
        request: Request,
        exc: AuthApiError,
    ) -> JSONResponse:
        """Convert domain auth errors into canonical HTTP responses."""
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
        """Convert unexpected exceptions into canonical error envelopes."""
        log = structlog.get_logger("errors")
        log.exception(
            "unhandled_exception",
            error_type=type(exc).__name__,
            request_id=_request_id(request=request),
        )
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


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Inject request ID into context and response headers."""
    request_id = bind_request_id(request)
    try:
        response = await call_next(request)
        return finalize_request_id(response, request_id=request_id)
    finally:
        unbind_request_id()


def _request_id(*, request: Request) -> str | None:
    """Extract request ID from request state or headers."""
    return request_id_from_request(request=request)


async def _parse_introspect_request(
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
