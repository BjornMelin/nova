"""FastAPI application factory and public runtime assembly seams."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware import Middleware
from starlette.types import Lifespan

from nova_file_api.config import Settings
from nova_file_api.exception_handlers import register_exception_handlers
from nova_file_api.openapi import install_openapi_override
from nova_file_api.routes import (
    exports_router,
    ops_router,
    platform_router,
    transfer_router,
)
from nova_file_api.runtime import (
    ApiRuntime,
    bootstrap_api_runtime,
    clear_runtime,
    install_runtime,
)
from nova_runtime_support.http import RequestContextASGIMiddleware
from nova_runtime_support.logging import configure_structlog

_CORS_ALLOWED_HEADERS = [
    "Authorization",
    "Content-Type",
    "Idempotency-Key",
    "X-Request-Id",
]
_CORS_ALLOWED_METHODS = ["GET", "POST", "OPTIONS"]
_CORS_EXPOSE_HEADERS = ["ETag", "X-Request-Id"]
_OPENAPI_DESCRIPTION = (
    "Typed control-plane API for direct-to-S3 uploads, presigned downloads, "
    "and durable export workflows.\n\n"
    "This API coordinates transfer policy discovery, multipart session state, "
    "and export workflow lifecycle metadata. It is not a bulk data-plane "
    "proxy; clients transfer object bytes directly with S3 using the returned "
    "metadata."
)
_OPENAPI_TAGS = [
    {
        "name": "transfers",
        "description": (
            "Direct-to-S3 upload and download planning endpoints, including "
            "multipart session orchestration."
        ),
    },
    {
        "name": "exports",
        "description": (
            "Durable export workflow resources used to create, inspect, list, "
            "and cancel caller-owned exports."
        ),
    },
    {
        "name": "platform",
        "description": (
            "Capability, release, and supportability endpoints that describe "
            "the current deployment contract."
        ),
    },
    {
        "name": "ops",
        "description": (
            "Operational liveness, readiness, and metrics endpoints for "
            "runtime health and observability."
        ),
    },
]


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


def _managed_runtime_lifespan(*, settings: Settings) -> Lifespan[FastAPI]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        bootstrap = await bootstrap_api_runtime(settings=settings)
        install_runtime(app=app, runtime=bootstrap.runtime)
        try:
            yield
        finally:
            await bootstrap.aclose()
            clear_runtime(app=app)

    return lifespan


def _build_app(
    *,
    settings: Settings,
    lifespan: Lifespan[FastAPI] | None = None,
    runtime: ApiRuntime | None = None,
) -> FastAPI:
    app = FastAPI(
        title="nova-file-api",
        description=_OPENAPI_DESCRIPTION,
        version=settings.app_version,
        lifespan=lifespan,
        middleware=_cors_middleware(settings=settings),
        openapi_tags=_OPENAPI_TAGS,
        strict_content_type=True,
    )
    app.add_middleware(cast(Any, RequestContextASGIMiddleware))
    if runtime is not None:
        install_runtime(app=app, runtime=runtime)
    install_openapi_override(app=app)

    app.include_router(ops_router)
    app.include_router(transfer_router)
    app.include_router(exports_router)
    app.include_router(platform_router)
    register_exception_handlers(app)

    return app


def create_app(
    *,
    runtime: ApiRuntime,
) -> FastAPI:
    """Create a FastAPI app around a prebuilt runtime container."""
    configure_structlog()
    return _build_app(
        settings=runtime.settings,
        runtime=runtime,
    )


def create_managed_app(*, settings: Settings | None = None) -> FastAPI:
    """Create a FastAPI app that owns runtime bootstrap in lifespan."""
    configure_structlog()
    resolved_settings = Settings() if settings is None else settings
    return _build_app(
        settings=resolved_settings,
        lifespan=_managed_runtime_lifespan(settings=resolved_settings),
    )


__all__ = ["create_app", "create_managed_app"]
