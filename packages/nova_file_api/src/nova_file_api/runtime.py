"""Runtime container and bootstrap helpers for the file API."""

from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import cast

import aioboto3
import structlog
from fastapi import FastAPI

from nova_file_api.activity import (
    ActivityStore,
    DynamoActivityStore,
    DynamoResource as ActivityDynamoResource,
    MemoryActivityStore,
)
from nova_file_api.auth import Authenticator, SupportsAuthenticatorAsyncClose
from nova_file_api.aws import aws_client_config, s3_client_config
from nova_file_api.cache import LocalTTLCache, TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.export_runtime import (
    DynamoExportRepository,
    DynamoResource,
    ExportPublisher,
    ExportRepository,
    MemoryExportPublisher,
    MemoryExportRepository,
    StepFunctionsClient,
    StepFunctionsExportPublisher,
)
from nova_file_api.exports import ExportService
from nova_file_api.idempotency import (
    DynamoResource as IdempotencyDynamoResource,
    IdempotencyStore,
)
from nova_file_api.models import ActivityStoreBackend
from nova_file_api.transfer import TransferService
from nova_file_api.transfer_config import transfer_config_from_settings
from nova_file_api.transfer_policy import (
    AppConfigDataClient,
    build_transfer_policy_provider,
)
from nova_file_api.transfer_usage import (
    DynamoResource as TransferUsageDynamoResource,
    build_transfer_usage_window_repository,
)
from nova_file_api.upload_sessions import (
    DynamoResource as UploadSessionDynamoResource,
    build_upload_session_repository,
)
from nova_runtime_support.metrics import MetricsCollector

_LOGGER = structlog.get_logger("nova_file_api.runtime")
_MSG_EXPORTS_DYNAMODB_TABLE_REQUIRED = (
    "EXPORTS_DYNAMODB_TABLE must be configured when EXPORTS_ENABLED=true"
)
_MSG_ACTIVITY_ROLLUPS_TABLE_REQUIRED = (
    "ACTIVITY_ROLLUPS_TABLE must be configured when "
    "ACTIVITY_STORE_BACKEND=dynamodb"
)
_MSG_IDEMPOTENCY_REQUIRES_DYNAMODB_TABLE = (
    "IDEMPOTENCY_DYNAMODB_TABLE must be configured when "
    "IDEMPOTENCY_ENABLED=true"
)
_MSG_S3_CLIENT_REQUIRED = "s3_client must be provided"
_MSG_DYNAMODB_RESOURCE_REQUIRED = (
    "dynamodb_resource must be provided when DynamoDB backends are enabled"
)
_MSG_STEP_FUNCTIONS_STATE_MACHINE_ARN_REQUIRED = (
    "EXPORT_WORKFLOW_STATE_MACHINE_ARN must be configured when "
    "EXPORTS_ENABLED=true"
)
_MSG_STEP_FUNCTIONS_CLIENT_REQUIRED = (
    "stepfunctions_client must be provided when EXPORTS_ENABLED=true"
)


@dataclass(slots=True)
class ApiRuntime:
    """Typed runtime container installed on ``app.state.runtime``."""

    settings: Settings
    metrics: MetricsCollector
    cache: TwoTierCache
    authenticator: Authenticator
    transfer_service: TransferService
    export_repository: ExportRepository
    export_service: ExportService
    activity_store: ActivityStore
    idempotency_store: IdempotencyStore


@dataclass(slots=True)
class RuntimeBootstrap:
    """Own the lifecycle for one bootstrapped runtime container."""

    runtime: ApiRuntime
    _exit_stack: AsyncExitStack | None = field(repr=False, default=None)

    async def aclose(self) -> None:
        """Release runtime-owned resources."""
        try:
            if isinstance(
                self.runtime.authenticator,
                SupportsAuthenticatorAsyncClose,
            ):
                await self.runtime.authenticator.aclose()
        except Exception:
            _LOGGER.exception("runtime_authenticator_close_failed")
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None


def install_runtime(*, app: FastAPI, runtime: ApiRuntime) -> None:
    """Install the typed runtime container on a FastAPI app."""
    app.state.runtime = runtime


def clear_runtime(*, app: FastAPI) -> None:
    """Clear the typed runtime container from a FastAPI app."""
    if hasattr(app.state, "runtime"):
        app.state.runtime = None


def build_metrics(*, settings: Settings) -> MetricsCollector:
    """Create the metrics collector for the current settings."""
    return MetricsCollector(namespace=settings.metrics_namespace)


def build_two_tier_cache(
    *,
    settings: Settings,
    metrics: MetricsCollector,
) -> TwoTierCache:
    """Create the local runtime cache used by auth and cached lookups."""
    return TwoTierCache(
        local=LocalTTLCache(
            ttl_seconds=settings.cache_local_ttl_seconds,
            max_entries=settings.cache_local_max_entries,
        ),
        key_prefix=settings.cache_key_prefix,
        key_schema_version=settings.cache_key_schema_version,
        metric_incr=metrics.incr,
    )


def build_idempotency_store(
    *,
    settings: Settings,
    dynamodb_resource: object | None,
) -> IdempotencyStore:
    """Create the idempotency store."""
    table_name = (settings.idempotency_dynamodb_table or "").strip()
    if settings.idempotency_enabled:
        if not table_name:
            raise ValueError(_MSG_IDEMPOTENCY_REQUIRES_DYNAMODB_TABLE)
        if dynamodb_resource is None:
            raise ValueError(_MSG_DYNAMODB_RESOURCE_REQUIRED)
    return IdempotencyStore(
        table_name=table_name or None,
        dynamodb_resource=cast(
            IdempotencyDynamoResource | None,
            dynamodb_resource,
        ),
        enabled=settings.idempotency_enabled,
        ttl_seconds=settings.idempotency_ttl_seconds,
        key_prefix=settings.cache_key_prefix,
        key_schema_version=settings.cache_key_schema_version,
    )


def build_authenticator(
    *,
    settings: Settings,
    cache: TwoTierCache,
) -> Authenticator:
    """Create the request authenticator."""
    return Authenticator(settings=settings, cache=cache)


def build_transfer_service(
    *,
    settings: Settings,
    s3_client: object,
    accelerate_s3_client: object | None = None,
    dynamodb_resource: object | None = None,
    appconfig_client: object | None = None,
) -> TransferService:
    """Create the transfer service."""
    transfer_config = transfer_config_from_settings(settings)
    upload_session_repository = build_upload_session_repository(
        table_name=settings.file_transfer_upload_sessions_table,
        dynamodb_resource=cast(
            UploadSessionDynamoResource | None,
            dynamodb_resource,
        ),
        enabled=settings.file_transfer_enabled,
    )
    transfer_usage_repository = build_transfer_usage_window_repository(
        table_name=settings.file_transfer_usage_table,
        dynamodb_resource=cast(
            TransferUsageDynamoResource | None,
            dynamodb_resource,
        ),
        enabled=settings.file_transfer_enabled,
    )
    return TransferService(
        config=transfer_config,
        s3_client=s3_client,
        accelerate_s3_client=accelerate_s3_client,
        policy_provider=build_transfer_policy_provider(
            config=transfer_config,
            appconfig_client=cast(
                AppConfigDataClient | None,
                appconfig_client,
            ),
        ),
        upload_session_repository=upload_session_repository,
        transfer_usage_repository=transfer_usage_repository,
    )


def build_export_repository(
    *,
    settings: Settings,
    dynamodb_resource: object | None,
) -> ExportRepository:
    """Create the configured export repository."""
    exports_table = (
        settings.exports_dynamodb_table.strip()
        if settings.exports_dynamodb_table
        else ""
    )
    if settings.exports_enabled:
        if not exports_table:
            raise ValueError(_MSG_EXPORTS_DYNAMODB_TABLE_REQUIRED)
        if dynamodb_resource is None:
            raise ValueError(_MSG_DYNAMODB_RESOURCE_REQUIRED)
        return DynamoExportRepository(
            table_name=exports_table,
            dynamodb_resource=cast(DynamoResource, dynamodb_resource),
        )
    return MemoryExportRepository()


def build_export_publisher(
    *,
    settings: Settings,
    stepfunctions_client: object | None,
) -> ExportPublisher:
    """Create the configured export publisher."""
    if settings.exports_enabled:
        state_machine_arn = (
            settings.export_workflow_state_machine_arn.strip()
            if settings.export_workflow_state_machine_arn
            else None
        )
        if not state_machine_arn:
            raise ValueError(_MSG_STEP_FUNCTIONS_STATE_MACHINE_ARN_REQUIRED)
        if stepfunctions_client is None:
            raise ValueError(_MSG_STEP_FUNCTIONS_CLIENT_REQUIRED)
        return StepFunctionsExportPublisher(
            state_machine_arn=state_machine_arn,
            stepfunctions_client=cast(
                StepFunctionsClient,
                stepfunctions_client,
            ),
        )
    return MemoryExportPublisher(
        export_prefix=settings.file_transfer_export_prefix
    )


def build_export_service(
    *,
    export_repository: ExportRepository,
    export_publisher: ExportPublisher,
    metrics: MetricsCollector,
) -> ExportService:
    """Create the export service."""
    return ExportService(
        repository=export_repository,
        publisher=export_publisher,
        metrics=metrics,
    )


def build_activity_store(
    *,
    settings: Settings,
    dynamodb_resource: object | None,
) -> ActivityStore:
    """Create the configured activity store."""
    if settings.activity_store_backend == ActivityStoreBackend.DYNAMODB:
        rollups_table = (
            settings.activity_rollups_table.strip()
            if settings.activity_rollups_table
            else ""
        )
        if not rollups_table:
            raise ValueError(_MSG_ACTIVITY_ROLLUPS_TABLE_REQUIRED)
        if dynamodb_resource is None:
            raise ValueError(_MSG_DYNAMODB_RESOURCE_REQUIRED)
        return DynamoActivityStore(
            table_name=rollups_table,
            dynamodb_resource=cast(ActivityDynamoResource, dynamodb_resource),
        )
    return MemoryActivityStore()


def build_api_runtime(
    *,
    settings: Settings,
    s3_client: object,
    accelerate_s3_client: object | None = None,
    dynamodb_resource: object | None = None,
    stepfunctions_client: object | None = None,
    appconfig_client: object | None = None,
) -> ApiRuntime:
    """Assemble one typed runtime container from configured dependencies."""
    if s3_client is None:
        raise ValueError(_MSG_S3_CLIENT_REQUIRED)

    metrics = build_metrics(settings=settings)
    cache = build_two_tier_cache(settings=settings, metrics=metrics)
    export_repository = build_export_repository(
        settings=settings,
        dynamodb_resource=dynamodb_resource,
    )
    export_publisher = build_export_publisher(
        settings=settings,
        stepfunctions_client=stepfunctions_client,
    )
    activity_store = build_activity_store(
        settings=settings,
        dynamodb_resource=dynamodb_resource,
    )
    idempotency_store = build_idempotency_store(
        settings=settings,
        dynamodb_resource=dynamodb_resource,
    )
    return ApiRuntime(
        settings=settings,
        metrics=metrics,
        cache=cache,
        authenticator=build_authenticator(settings=settings, cache=cache),
        transfer_service=build_transfer_service(
            settings=settings,
            s3_client=s3_client,
            accelerate_s3_client=accelerate_s3_client,
            dynamodb_resource=dynamodb_resource,
            appconfig_client=appconfig_client,
        ),
        export_repository=export_repository,
        export_service=build_export_service(
            export_repository=export_repository,
            export_publisher=export_publisher,
            metrics=metrics,
        ),
        activity_store=activity_store,
        idempotency_store=idempotency_store,
    )


def _requires_dynamodb(settings: Settings) -> bool:
    return (
        settings.file_transfer_enabled
        or settings.idempotency_enabled
        or settings.exports_enabled
        or settings.activity_store_backend == ActivityStoreBackend.DYNAMODB
    )


def _requires_stepfunctions(settings: Settings) -> bool:
    return settings.exports_enabled and bool(
        settings.export_workflow_state_machine_arn
        and settings.export_workflow_state_machine_arn.strip()
    )


def _requires_appconfig(settings: Settings) -> bool:
    appconfig_identifiers = {
        "FILE_TRANSFER_POLICY_APPCONFIG_APPLICATION": (
            settings.file_transfer_policy_appconfig_application
        ),
        "FILE_TRANSFER_POLICY_APPCONFIG_ENVIRONMENT": (
            settings.file_transfer_policy_appconfig_environment
        ),
        "FILE_TRANSFER_POLICY_APPCONFIG_PROFILE": (
            settings.file_transfer_policy_appconfig_profile
        ),
    }
    configured_identifiers = {
        name: value.strip()
        for name, value in appconfig_identifiers.items()
        if isinstance(value, str) and value.strip()
    }
    if configured_identifiers and len(configured_identifiers) != len(
        appconfig_identifiers
    ):
        missing_identifiers = sorted(
            set(appconfig_identifiers) - set(configured_identifiers)
        )
        missing = ", ".join(missing_identifiers)
        raise ValueError(
            "Transfer policy AppConfig settings must be configured "
            f"together; missing: {missing}"
        )
    return len(configured_identifiers) == len(appconfig_identifiers)


async def bootstrap_api_runtime(*, settings: Settings) -> RuntimeBootstrap:
    """Create one managed runtime container for local or Lambda reuse."""
    session = aioboto3.Session()
    exit_stack = AsyncExitStack()
    try:
        s3_client = await exit_stack.enter_async_context(
            session.client(
                "s3",
                config=s3_client_config(use_accelerate_endpoint=False),
            )
        )
        accelerate_s3_client = await exit_stack.enter_async_context(
            session.client(
                "s3",
                config=s3_client_config(use_accelerate_endpoint=True),
            )
        )
        dynamodb_resource = None
        if _requires_dynamodb(settings):
            dynamodb_resource = await exit_stack.enter_async_context(
                session.resource("dynamodb", config=aws_client_config())
            )
        stepfunctions_client = None
        if _requires_stepfunctions(settings):
            stepfunctions_client = await exit_stack.enter_async_context(
                session.client("stepfunctions", config=aws_client_config())
            )
        appconfig_client = None
        if _requires_appconfig(settings):
            appconfig_client = await exit_stack.enter_async_context(
                session.client("appconfigdata", config=aws_client_config())
            )
        runtime = build_api_runtime(
            settings=settings,
            s3_client=s3_client,
            accelerate_s3_client=accelerate_s3_client,
            dynamodb_resource=dynamodb_resource,
            stepfunctions_client=stepfunctions_client,
            appconfig_client=appconfig_client,
        )
        return RuntimeBootstrap(runtime=runtime, _exit_stack=exit_stack)
    except Exception:
        await exit_stack.aclose()
        raise


__all__ = [
    "ApiRuntime",
    "RuntimeBootstrap",
    "bootstrap_api_runtime",
    "build_activity_store",
    "build_api_runtime",
    "build_authenticator",
    "build_export_publisher",
    "build_export_repository",
    "build_export_service",
    "build_idempotency_store",
    "build_metrics",
    "build_transfer_service",
    "build_two_tier_cache",
    "clear_runtime",
    "install_runtime",
]
