"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import structlog
from botocore.config import Config
from fastapi import FastAPI
from nova_runtime_support import (
    RequestContextFastAPI,
    configure_structlog,
)

from nova_file_api.aws import new_aioboto3_session
from nova_file_api.config import Settings
from nova_file_api.dependencies import initialize_runtime_state
from nova_file_api.exception_handlers import register_exception_handlers
from nova_file_api.models import (
    ActivityStoreBackend,
    JobsQueueBackend,
    JobsRepositoryBackend,
)
from nova_file_api.routes import (
    jobs_router,
    ops_router,
    platform_router,
    transfer_router,
)

_LOGGER = structlog.get_logger("nova_file_api.app")
_RUNTIME_STATE_KEYS = (
    "metrics",
    "shared_cache",
    "cache",
    "authenticator",
    "transfer_service",
    "job_repository",
    "job_service",
    "activity_store",
    "idempotency_store",
)


async def _close_authenticator(*, app: FastAPI) -> None:
    """Close the app authenticator when it exposes an async close hook."""
    close_authenticator = getattr(
        getattr(app.state, "authenticator", None), "aclose", None
    )
    if callable(close_authenticator):
        await close_authenticator()


async def _close_shared_cache(*, app: FastAPI) -> None:
    """Close the app shared cache when it exposes an async close hook."""
    close_shared_cache = getattr(
        getattr(app.state, "shared_cache", None), "aclose", None
    )
    if callable(close_shared_cache):
        await close_shared_cache()


def _clear_runtime_state(*, app: FastAPI) -> None:
    """Invalidate runtime-owned singletons so the next lifespan rebuilds."""
    for key in _RUNTIME_STATE_KEYS:
        if hasattr(app.state, key):
            setattr(app.state, key, None)


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
            if manage_runtime_state:
                try:
                    await _close_authenticator(app=app)
                except Exception:
                    _LOGGER.exception(
                        "runtime_state_authenticator_close_failed"
                    )
                try:
                    await _close_shared_cache(app=app)
                except Exception:
                    _LOGGER.exception("runtime_state_shared_cache_close_failed")
                _clear_runtime_state(app=app)

    app = RequestContextFastAPI(
        title="nova-file-api",
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.include_router(ops_router)
    app.include_router(transfer_router)
    app.include_router(jobs_router)
    app.include_router(platform_router)
    register_exception_handlers(app)

    return app
