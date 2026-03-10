"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import aioboto3  # type: ignore[import-untyped]
from botocore.config import Config
from fastapi import FastAPI
from nova_runtime_support import configure_structlog

from nova_file_api.config import Settings
from nova_file_api.container import AppContainer, create_container
from nova_file_api.exception_handlers import register_exception_handlers
from nova_file_api.middleware import request_context_middleware
from nova_file_api.models import (
    ActivityStoreBackend,
    JobsQueueBackend,
    JobsRepositoryBackend,
)
from nova_file_api.openapi import install_file_api_openapi_overrides
from nova_file_api.routes import ops_router, transfer_router, v1_router


async def _close_authenticator(*, container: AppContainer) -> None:
    """Close a container authenticator when it exposes an async close hook."""
    close_authenticator = getattr(container.authenticator, "aclose", None)
    if callable(close_authenticator):
        await close_authenticator()


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
        if container_override is not None:
            app.state.container = container_override
            try:
                yield
            finally:
                await _close_authenticator(container=app.state.container)
            return

        session = aioboto3.Session()
        s3_config = Config(
            s3={
                "use_accelerate_endpoint": (
                    settings.file_transfer_use_accelerate_endpoint
                )
            }
        )
        requires_dynamodb = (
            settings.jobs_repository_backend == JobsRepositoryBackend.DYNAMODB
            or settings.activity_store_backend == ActivityStoreBackend.DYNAMODB
        )
        requires_sqs = (
            settings.jobs_enabled
            and settings.jobs_queue_backend == JobsQueueBackend.SQS
            and bool(
                settings.jobs_sqs_queue_url
                and settings.jobs_sqs_queue_url.strip()
            )
        )
        async with AsyncExitStack() as stack:
            s3_client = await stack.enter_async_context(
                session.client("s3", config=s3_config)
            )
            dynamodb_resource = None
            if requires_dynamodb:
                dynamodb_resource = await stack.enter_async_context(
                    session.resource("dynamodb")
                )
            sqs_client = None
            if requires_sqs:
                sqs_config = Config(
                    retries={
                        "mode": settings.jobs_sqs_retry_mode,
                        "total_max_attempts": (
                            settings.jobs_sqs_retry_total_max_attempts
                        ),
                    }
                )
                sqs_client = await stack.enter_async_context(
                    session.client("sqs", config=sqs_config)
                )
            app.state.container = create_container(
                settings=settings,
                s3_client=s3_client,
                dynamodb_resource=dynamodb_resource,
                sqs_client=sqs_client,
            )
            try:
                yield
            finally:
                await _close_authenticator(container=app.state.container)

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
