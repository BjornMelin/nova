"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, cast

import aioboto3
import structlog
from botocore.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware import Middleware

from nova_file_api.auth import SupportsAuthenticatorAsyncClose
from nova_file_api.config import Settings
from nova_file_api.dependencies import initialize_runtime_state
from nova_file_api.exception_handlers import register_exception_handlers
from nova_file_api.models import ActivityStoreBackend
from nova_file_api.routes import (
    exports_router,
    ops_router,
    platform_router,
    transfer_router,
)
from nova_runtime_support.http import RequestContextASGIMiddleware
from nova_runtime_support.logging import configure_structlog

_LOGGER = structlog.get_logger("nova_file_api.app")
_RUNTIME_STATE_KEYS = (
    "metrics",
    "cache",
    "authenticator",
    "transfer_service",
    "export_repository",
    "export_service",
    "activity_store",
    "idempotency_store",
)
_CORS_ALLOWED_HEADERS = [
    "Authorization",
    "Content-Type",
    "Idempotency-Key",
    "X-Request-Id",
]
_CORS_ALLOWED_METHODS = ["GET", "POST", "OPTIONS"]
_CORS_EXPOSE_HEADERS = ["ETag", "X-Request-Id"]

# Cap HTTPValidationError.detail[] (FastAPI how-to: extending-openapi).
_HTTP_VALIDATION_ERROR_DETAIL_MAX_ITEMS = 256
_HTTP_VALIDATION_ERROR_LOC_MAX_ITEMS = 32
_HTTP_VALIDATION_ERROR_DESCRIPTION = (
    "Validation error envelope returned for invalid request payloads."
)
_VALIDATION_ERROR_DESCRIPTION = (
    "One request-validation issue with location, message, and error type."
)


def _patch_http_validation_error_detail_max_items(
    schema: dict[str, Any],
) -> None:
    """Patch validation-error schemas for bounded and documented output."""
    schemas = schema.get("components", {}).get("schemas", {})
    if not isinstance(schemas, dict):
        return
    http_validation_error = schemas.get("HTTPValidationError", {})
    validation_error = schemas.get("ValidationError", {})

    if isinstance(http_validation_error, dict):
        http_validation_error.setdefault(
            "description",
            _HTTP_VALIDATION_ERROR_DESCRIPTION,
        )
    if isinstance(validation_error, dict):
        validation_error.setdefault(
            "description",
            _VALIDATION_ERROR_DESCRIPTION,
        )

    detail = (
        http_validation_error.get("properties", {}).get("detail")
        if isinstance(http_validation_error, dict)
        else None
    )
    if isinstance(detail, dict) and detail.get("type") == "array":
        detail["maxItems"] = _HTTP_VALIDATION_ERROR_DETAIL_MAX_ITEMS
    loc = (
        validation_error.get("properties", {}).get("loc")
        if isinstance(validation_error, dict)
        else None
    )
    if isinstance(loc, dict) and loc.get("type") == "array":
        loc["maxItems"] = _HTTP_VALIDATION_ERROR_LOC_MAX_ITEMS


def _install_openapi_override(*, app: FastAPI) -> None:
    """Install the documented FastAPI OpenAPI override on one app instance."""
    original_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        schema = app.openapi_schema
        if schema is not None:
            return schema
        schema = original_openapi()
        _patch_http_validation_error_detail_max_items(schema)
        app.openapi_schema = schema
        return schema

    app.__dict__["openapi"] = custom_openapi


async def _close_authenticator(*, app: FastAPI) -> None:
    """Close the app authenticator when it exposes an async close hook."""
    authenticator = getattr(app.state, "authenticator", None)
    if authenticator is None:
        return
    if isinstance(authenticator, SupportsAuthenticatorAsyncClose):
        await authenticator.aclose()


def _clear_runtime_state(*, app: FastAPI) -> None:
    """Invalidate runtime-owned singletons so the next lifespan rebuilds."""
    for key in _RUNTIME_STATE_KEYS:
        if hasattr(app.state, key):
            setattr(app.state, key, None)


def _cors_middleware(*, settings: Settings) -> list[Middleware]:
    """Build CORS middleware when allowed origins are configured."""
    allowed_origins = list(settings.resolved_cors_allowed_origins)
    if not allowed_origins:
        return []
    return [
        Middleware(
            cast(Any, CORSMiddleware),
            allow_origins=allowed_origins,
            allow_credentials=False,
            allow_methods=_CORS_ALLOWED_METHODS,
            allow_headers=_CORS_ALLOWED_HEADERS,
            expose_headers=_CORS_EXPOSE_HEADERS,
        ),
    ]


def create_app(*, settings: Settings | None = None) -> FastAPI:
    """Create a configured FastAPI application.

    Args:
        settings: Optional prebuilt settings. When omitted, a new settings
            object is resolved from the environment.

    Returns:
        Configured FastAPI application.
    """
    configure_structlog()
    settings = Settings() if settings is None else settings

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        manage_runtime_state = not getattr(
            app.state, "_skip_runtime_state_initialization", False
        )
        try:
            if not manage_runtime_state:
                yield
            else:
                runtime_settings = app.state.settings
                session = aioboto3.Session()
                standard_s3_config = Config(
                    s3={"use_accelerate_endpoint": False}
                )
                accelerate_s3_config = Config(
                    s3={"use_accelerate_endpoint": True}
                )
                requires_dynamodb = (
                    runtime_settings.file_transfer_enabled
                    or runtime_settings.idempotency_enabled
                    or runtime_settings.exports_enabled
                    or runtime_settings.activity_store_backend
                    == ActivityStoreBackend.DYNAMODB
                )
                requires_stepfunctions = (
                    runtime_settings.exports_enabled
                    and bool(
                        runtime_settings.export_workflow_state_machine_arn
                        and (
                            runtime_settings.export_workflow_state_machine_arn.strip()
                        )
                    )
                )
                appconfig_identifiers = {
                    "FILE_TRANSFER_POLICY_APPCONFIG_APPLICATION": (
                        runtime_settings.file_transfer_policy_appconfig_application
                    ),
                    "FILE_TRANSFER_POLICY_APPCONFIG_ENVIRONMENT": (
                        runtime_settings.file_transfer_policy_appconfig_environment
                    ),
                    "FILE_TRANSFER_POLICY_APPCONFIG_PROFILE": (
                        runtime_settings.file_transfer_policy_appconfig_profile
                    ),
                }
                configured_appconfig_identifiers = {
                    name: value.strip()
                    for name, value in appconfig_identifiers.items()
                    if isinstance(value, str) and value.strip()
                }
                requires_appconfig = len(
                    configured_appconfig_identifiers
                ) == len(appconfig_identifiers)
                if configured_appconfig_identifiers and not requires_appconfig:
                    missing_identifiers = sorted(
                        set(appconfig_identifiers)
                        - set(configured_appconfig_identifiers)
                    )
                    missing = ", ".join(missing_identifiers)
                    raise ValueError(
                        "Transfer policy AppConfig settings must be configured "
                        f"together; missing: {missing}"
                    )

                async with AsyncExitStack() as stack:
                    s3_client = await stack.enter_async_context(
                        session.client("s3", config=standard_s3_config)
                    )
                    accelerate_s3_client = await stack.enter_async_context(
                        session.client("s3", config=accelerate_s3_config)
                    )
                    dynamodb_resource = None
                    if requires_dynamodb:
                        dynamodb_resource = await stack.enter_async_context(
                            session.resource("dynamodb")
                        )
                    stepfunctions_client = None
                    if requires_stepfunctions:
                        stepfunctions_client = await stack.enter_async_context(
                            session.client("stepfunctions")
                        )
                    appconfig_client = None
                    if requires_appconfig:
                        appconfig_client = await stack.enter_async_context(
                            session.client("appconfigdata")
                        )

                    runtime_state_kwargs = {
                        "settings": runtime_settings,
                        "s3_client": s3_client,
                        "accelerate_s3_client": accelerate_s3_client,
                        "dynamodb_resource": dynamodb_resource,
                    }
                    if stepfunctions_client is not None:
                        runtime_state_kwargs["stepfunctions_client"] = (
                            stepfunctions_client
                        )
                    if appconfig_client is not None:
                        runtime_state_kwargs["appconfig_client"] = (
                            appconfig_client
                        )

                    initialize_runtime_state(
                        app,
                        **runtime_state_kwargs,
                    )
                    yield
        finally:
            if manage_runtime_state:
                try:
                    await _close_authenticator(app=app)
                except Exception:
                    _LOGGER.exception(
                        "runtime_state_authenticator_close_failed"
                    )
                try:
                    _clear_runtime_state(app=app)
                except Exception:
                    _LOGGER.exception("runtime_state_clear_failed")

    app = FastAPI(
        title="nova-file-api",
        version=settings.app_version,
        lifespan=lifespan,
        middleware=_cors_middleware(settings=settings),
        strict_content_type=True,
    )
    app.add_middleware(cast(Any, RequestContextASGIMiddleware))
    app.state.settings = settings
    _install_openapi_override(app=app)

    app.include_router(ops_router)
    app.include_router(transfer_router)
    app.include_router(exports_router)
    app.include_router(platform_router)
    register_exception_handlers(app)

    return app
