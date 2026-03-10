"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aioboto3  # type: ignore[import-untyped]
from botocore.config import Config
from fastapi import FastAPI
from nova_runtime_support import configure_structlog

from nova_file_api.config import Settings
from nova_file_api.container import AppContainer, create_container
from nova_file_api.exception_handlers import register_exception_handlers
from nova_file_api.middleware import request_context_middleware
from nova_file_api.openapi import install_file_api_openapi_overrides
from nova_file_api.routes import ops_router, transfer_router, v1_router


def create_app(*, container_override: AppContainer | None = None) -> FastAPI:
    """
    Create and configure a FastAPI application for nova-file-api.
    
    The returned application is initialized with the lifecycle manager that sets up
    and tears down the dependency container (or attaches the provided override),
    registers middleware, routers, OpenAPI overrides, and exception handlers.
    
    Parameters:
        container_override (AppContainer | None): Optional prebuilt application
            container to attach to the app instead of creating one. If provided,
            the container is used as-is and, if its `authenticator` exposes an
            `aclose` coroutine, that coroutine will be awaited on shutdown.
    
    Returns:
        FastAPI: A FastAPI application instance configured with the project's
        routers, middleware, lifespan, and exception handlers.
    """
    configure_structlog()
    settings = (
        container_override.settings
        if container_override is not None
        else Settings()
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """
        Manage application lifespan by attaching settings and a dependency container to app.state and ensuring the container's authenticator is closed on shutdown.
        
        If a container_override is provided, it is attached to app.state.container and its `authenticator.aclose()` coroutine is awaited on shutdown when present. If no override is provided, AWS clients/resources are created, an application container is instantiated and attached to app.state.container for the app lifetime, and that container's `authenticator.aclose()` coroutine is awaited on shutdown when present.
        """
        app.state.settings = settings
        if container_override is not None:
            app.state.container = container_override
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
            return

        session = aioboto3.Session()
        s3_config = Config(
            s3={
                "use_accelerate_endpoint": (
                    settings.file_transfer_use_accelerate_endpoint
                )
            }
        )
        sqs_config = Config(
            retries={
                "mode": settings.jobs_sqs_retry_mode,
                "total_max_attempts": (
                    settings.jobs_sqs_retry_total_max_attempts
                ),
            }
        )
        async with (
            session.client("s3", config=s3_config) as s3_client,
            session.resource("dynamodb") as dynamodb_resource,
            session.client("sqs", config=sqs_config) as sqs_client,
        ):
            app.state.container = create_container(
                settings=settings,
                s3_client=s3_client,
                dynamodb_resource=dynamodb_resource,
                sqs_client=sqs_client,
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
        lifespan=lifespan,
    )
    install_file_api_openapi_overrides(app)

    app.middleware("http")(request_context_middleware)
    app.include_router(ops_router)
    app.include_router(transfer_router)
    app.include_router(v1_router)
    register_exception_handlers(app)

    return app