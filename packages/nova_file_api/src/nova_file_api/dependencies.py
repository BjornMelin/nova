"""FastAPI dependency helpers and runtime state assembly.

Dependency getters (get_settings, get_metrics, etc.) raise TypeError when
application state is not initialized. Build factories for DynamoDB/export
workflow backends raise ValueError when required config is missing.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from nova_file_api.activity import (
    ActivityStore,
    DynamoActivityStore,
    DynamoResource as ActivityDynamoResource,
    MemoryActivityStore,
)
from nova_file_api.auth import Authenticator
from nova_file_api.cache import LocalTTLCache, TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.exports import (
    ExportService,
)
from nova_file_api.idempotency import (
    DynamoResource as IdempotencyDynamoResource,
    IdempotencyStore,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import (
    ActivityStoreBackend,
    Principal,
)
from nova_file_api.transfer import TransferService
from nova_file_api.transfer_config import transfer_config_from_settings
from nova_file_api.transfer_policy import (
    AppConfigDataClient,
    build_transfer_policy_provider,
)
from nova_runtime_support.export_runtime import (
    DynamoExportRepository,
    DynamoResource,
    ExportPublisher,
    ExportRepository,
    MemoryExportPublisher,
    MemoryExportRepository,
    StepFunctionsClient,
    StepFunctionsExportPublisher,
)
from nova_runtime_support.transfer_usage import (
    DynamoResource as TransferUsageDynamoResource,
    build_transfer_usage_repository,
)
from nova_runtime_support.upload_sessions import (
    DynamoResource as UploadSessionDynamoResource,
    build_upload_session_repository,
)

_APPLICATION_STATE_NOT_INITIALIZED = "application state is not initialized"
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
_BEARER_AUTH = HTTPBearer(
    auto_error=False,
    scheme_name="bearerAuth",
    bearerFormat="JWT",
    description=(
        "Bearer JWT for public Nova file API requests. Scope and tenancy "
        "are derived from verified claims."
    ),
)


def initialize_runtime_state(
    app: FastAPI,
    *,
    settings: Settings,
    s3_client: object,
    dynamodb_resource: object | None = None,
    stepfunctions_client: object | None = None,
    appconfig_client: object | None = None,
) -> None:
    """Build and attach runtime singletons to application state.

    Args:
        app: FastAPI application receiving the singletons.
        settings: Resolved runtime settings.
        s3_client: Configured S3 client used by transfer services.
        dynamodb_resource: Optional DynamoDB resource for DynamoDB backends.
        stepfunctions_client: Optional Step Functions client for workflow-
            backed export dispatch.
        appconfig_client: Optional AppConfig Data client for transfer-policy
            overlays.

    Returns:
        None.

    Raises:
        ValueError: When runtime prerequisites are not met (missing s3_client,
            EXPORTS_DYNAMODB_TABLE, EXPORT_WORKFLOW_STATE_MACHINE_ARN, etc.).
    """
    if s3_client is None:
        raise ValueError(_MSG_S3_CLIENT_REQUIRED)

    metrics = build_metrics(settings=settings)

    cache_provider = getattr(app.state, "_two_tier_cache_provider", None)
    prebuilt_cache = cache_provider() if callable(cache_provider) else None
    existing_cache = getattr(app.state, "cache", None)
    cache: TwoTierCache
    if isinstance(prebuilt_cache, TwoTierCache):
        cache = prebuilt_cache
    elif isinstance(existing_cache, TwoTierCache):
        cache = existing_cache
    else:
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

    app.state.settings = settings
    app.state.metrics = metrics
    app.state.cache = cache
    app.state.authenticator = build_authenticator(
        settings=settings,
        cache=cache,
    )
    app.state.transfer_service = build_transfer_service(
        settings=settings,
        s3_client=s3_client,
        dynamodb_resource=dynamodb_resource,
        appconfig_client=appconfig_client,
    )
    app.state.export_repository = export_repository
    app.state.export_service = build_export_service(
        export_repository=export_repository,
        export_publisher=export_publisher,
        metrics=metrics,
    )
    app.state.activity_store = activity_store
    idempotency_store_provider = getattr(
        app.state, "_idempotency_store_provider", None
    )
    prebuilt_idempotency_store = (
        idempotency_store_provider()
        if callable(idempotency_store_provider)
        else None
    )
    existing_idempotency_store = getattr(app.state, "idempotency_store", None)
    if isinstance(prebuilt_idempotency_store, IdempotencyStore):
        idempotency_store = prebuilt_idempotency_store
    elif isinstance(existing_idempotency_store, IdempotencyStore):
        idempotency_store = existing_idempotency_store
    else:
        idempotency_store = build_idempotency_store(
            settings=settings,
            dynamodb_resource=dynamodb_resource,
        )
    app.state.idempotency_store = idempotency_store


def build_metrics(*, settings: Settings) -> MetricsCollector:
    """Create the metrics collector for the current settings."""
    return MetricsCollector(namespace=settings.metrics_namespace)


def build_two_tier_cache(
    *,
    settings: Settings,
    metrics: MetricsCollector,
) -> TwoTierCache:
    """Create the local runtime cache used by auth and cached lookups.

    Args:
        settings: Resolved runtime settings.
        metrics: Metrics collector for cache instrumentation.

    Returns:
        The configured runtime cache.
    """
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
    """Create the idempotency store.

    Args:
        settings: Resolved runtime settings.
        dynamodb_resource: DynamoDB resource when idempotency is enabled.

    Returns:
        The configured idempotency store.

    Raises:
        ValueError: When idempotency is enabled but the table name or DynamoDB
            resource is missing.
    """
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
    transfer_usage_repository = build_transfer_usage_repository(
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
    """Create the configured export repository.

    Args:
        settings: Resolved runtime settings.
        dynamodb_resource: DynamoDB resource when exports are enabled.

    Returns:
        The configured export repository.

    Raises:
        ValueError: When EXPORTS_DYNAMODB_TABLE is missing for exports,
            or dynamodb_resource is missing when required.
    """
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
    """Create the configured export publisher.

    Args:
        settings: Resolved runtime settings.
        stepfunctions_client: Step Functions client when exports are enabled.

    Returns:
        The configured export publisher.

    Raises:
        ValueError: When EXPORT_WORKFLOW_STATE_MACHINE_ARN is missing for
            enabled exports, or stepfunctions_client is missing when required.
    """
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
    """Create the export service.

    Args:
        export_repository: Configured export repository.
        export_publisher: Configured export publisher.
        metrics: Metrics collector for export instrumentation.

    Returns:
        The configured export service.
    """
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
    """Create the configured activity store.

    Args:
        settings: Resolved runtime settings.
        dynamodb_resource: DynamoDB resource when store backend is DynamoDB.
            Required when activity store backend is DynamoDB.

    Returns:
        The configured activity store.

    Raises:
        ValueError: When ACTIVITY_ROLLUPS_TABLE is missing for DynamoDB backend,
            or dynamodb_resource is missing when required.
    """
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


def get_settings(request: Request) -> Settings:
    """Return application settings from app state."""
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        raise TypeError(_APPLICATION_STATE_NOT_INITIALIZED)
    return cast(Settings, settings)


def get_metrics(request: Request) -> MetricsCollector:
    """Return the metrics collector from app state."""
    metrics = getattr(request.app.state, "metrics", None)
    if metrics is None:
        raise TypeError(_APPLICATION_STATE_NOT_INITIALIZED)
    return cast(MetricsCollector, metrics)


def get_two_tier_cache(request: Request) -> TwoTierCache:
    """Return the two-tier cache from app state."""
    cache = getattr(request.app.state, "cache", None)
    if cache is None:
        raise TypeError(_APPLICATION_STATE_NOT_INITIALIZED)
    return cast(TwoTierCache, cache)


def get_transfer_service(request: Request) -> TransferService:
    """Return the transfer service from app state."""
    transfer_service = getattr(request.app.state, "transfer_service", None)
    if transfer_service is None:
        raise TypeError(_APPLICATION_STATE_NOT_INITIALIZED)
    return cast(TransferService, transfer_service)


def get_export_repository(request: Request) -> ExportRepository:
    """Return the export repository from app state."""
    export_repository = getattr(request.app.state, "export_repository", None)
    if export_repository is None:
        raise TypeError(_APPLICATION_STATE_NOT_INITIALIZED)
    return cast(ExportRepository, export_repository)


def get_export_service(request: Request) -> ExportService:
    """Return the export service from app state."""
    export_service = getattr(request.app.state, "export_service", None)
    if export_service is None:
        raise TypeError(_APPLICATION_STATE_NOT_INITIALIZED)
    return cast(ExportService, export_service)


def get_activity_store(request: Request) -> ActivityStore:
    """Return the activity store from app state."""
    activity_store = getattr(request.app.state, "activity_store", None)
    if activity_store is None:
        raise TypeError(_APPLICATION_STATE_NOT_INITIALIZED)
    return cast(ActivityStore, activity_store)


def get_idempotency_store(request: Request) -> IdempotencyStore:
    """Return the idempotency store from app state."""
    idempotency_store = getattr(request.app.state, "idempotency_store", None)
    if idempotency_store is None:
        raise TypeError(_APPLICATION_STATE_NOT_INITIALIZED)
    return cast(IdempotencyStore, idempotency_store)


def get_authenticator(request: Request) -> Authenticator:
    """Return the authenticator from app state."""
    authenticator = getattr(request.app.state, "authenticator", None)
    if authenticator is None:
        raise TypeError(_APPLICATION_STATE_NOT_INITIALIZED)
    return cast(Authenticator, authenticator)


async def authenticate_principal(
    *,
    authenticator: Authenticator,
    credentials: HTTPAuthorizationCredentials | None,
) -> Principal:
    """Authenticate the current caller for a request."""
    return await authenticator.authenticate(
        token=(credentials.credentials if credentials is not None else None),
    )


async def get_principal(
    authenticator: Annotated[Authenticator, Depends(get_authenticator)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(_BEARER_AUTH),
    ],
) -> Principal:
    """Authenticate a bearer-authenticated public API request."""
    return await authenticate_principal(
        authenticator=authenticator,
        credentials=credentials,
    )


SettingsDep = Annotated[Settings, Depends(get_settings)]
MetricsDep = Annotated[MetricsCollector, Depends(get_metrics)]
TwoTierCacheDep = Annotated[TwoTierCache, Depends(get_two_tier_cache)]
TransferServiceDep = Annotated[TransferService, Depends(get_transfer_service)]
ExportRepositoryDep = Annotated[
    ExportRepository, Depends(get_export_repository)
]
ExportServiceDep = Annotated[ExportService, Depends(get_export_service)]
ActivityStoreDep = Annotated[ActivityStore, Depends(get_activity_store)]
IdempotencyStoreDep = Annotated[
    IdempotencyStore,
    Depends(get_idempotency_store),
]
AuthenticatorDep = Annotated[Authenticator, Depends(get_authenticator)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
