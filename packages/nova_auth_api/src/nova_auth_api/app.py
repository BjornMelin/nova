"""FastAPI application factory for nova-auth-api."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from nova_runtime_support import configure_structlog

from nova_auth_api.config import Settings
from nova_auth_api.exception_handlers import register_exception_handlers
from nova_auth_api.middleware import request_context_middleware
from nova_auth_api.openapi import install_auth_openapi
from nova_auth_api.routes import health_router, token_router
from nova_auth_api.service import TokenVerificationService


def create_app(
    *,
    settings_override: Settings | None = None,
    service_override: TokenVerificationService | None = None,
) -> FastAPI:
    """
    Create and configure a FastAPI application for nova-auth-api.
    
    Parameters:
        settings_override (Settings | None): Optional Settings instance to use instead of creating a new one. If provided, its values (including app_version) will be used during app creation.
        service_override (TokenVerificationService | None): Optional authentication service instance to attach to the application state as `app.state.auth_service`. If omitted, a default TokenVerificationService is created with the chosen settings.
    
    Returns:
        FastAPI: A FastAPI application with OpenAPI customization installed, request context middleware and exception handlers registered, health and token routers included, and `settings` and `auth_service` stored on `app.state`.
    """
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
        lifespan=lifespan,
    )
    install_auth_openapi(app)
    app.middleware("http")(request_context_middleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(token_router)
    return app
