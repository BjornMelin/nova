"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from botocore.config import Config
from fastapi import FastAPI
from nova_runtime_support import configure_structlog

from nova_file_api.aws import new_aioboto3_session
from nova_file_api.config import Settings
from nova_file_api.dependencies import initialize_runtime_state
from nova_file_api.exception_handlers import register_exception_handlers
from nova_file_api.middleware import request_context_middleware
from nova_file_api.models import (
    ActivityStoreBackend,
    JobsQueueBackend,
    JobsRepositoryBackend,
)
from nova_file_api.openapi import install_file_api_openapi_overrides
from nova_file_api.routes import (
    jobs_router,
    ops_router,
    platform_router,
    transfer_router,
)


async def _close_authenticator(*, app: FastAPI) -> None:
    """Close the app authenticator when it exposes an async close hook."""
    close_authenticator = getattr(
        getattr(app.state, "authenticator", None), "aclose", None
    )
    if callable(close_authenticator):
        await close_authenticator()


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
        try:
            if getattr(app.state, "_skip_runtime_state_initialization", False):
                yield
            else:
                runtime_settings = app.state.settings
                session = new_aioboto3_session()
                s3_config = Config(
                    s3={
                        "use_accelerate_endpoint": (
                            runtime_settings.file_transfer_use_accelerate_endpoint
                        )
                    }
                )
                requires_dynamodb = (
                    runtime_settings.jobs_repository_backend
                    == JobsRepositoryBackend.DYNAMODB
                    or runtime_settings.activity_store_backend
                    == ActivityStoreBackend.DYNAMODB
                )
                requires_sqs = (
                    runtime_settings.jobs_enabled
                    and runtime_settings.jobs_queue_backend
                    == JobsQueueBackend.SQS
                    and bool(
                        runtime_settings.jobs_sqs_queue_url
                        and runtime_settings.jobs_sqs_queue_url.strip()
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
                                "mode": runtime_settings.jobs_sqs_retry_mode,
                                "total_max_attempts": (
                                    runtime_settings.jobs_sqs_retry_total_max_attempts
                                ),
                            }
                        )
                        sqs_client = await stack.enter_async_context(
                            session.client("sqs", config=sqs_config)
                        )

                    initialize_runtime_state(
                        app,
                        settings=runtime_settings,
                        s3_client=s3_client,
                        dynamodb_resource=dynamodb_resource,
                        sqs_client=sqs_client,
                    )
                    yield
        finally:
            await _close_authenticator(app=app)

    app = FastAPI(
        title="nova-file-api",
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = settings
    install_file_api_openapi_overrides(app)

    app.middleware("http")(request_context_middleware)
    app.include_router(ops_router)
    app.include_router(transfer_router)
    app.include_router(jobs_router)
    app.include_router(platform_router)
    register_exception_handlers(app)

    return app
