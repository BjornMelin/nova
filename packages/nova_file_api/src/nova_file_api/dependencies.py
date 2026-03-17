"""FastAPI dependency helpers and runtime state assembly.

Dependency getters (get_settings, get_metrics, etc.) raise TypeError when
application state is not initialized. Build factories for DynamoDB/SQS backends
raise ValueError when required config is missing.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request

from nova_file_api.activity import (
    ActivityStore,
    DynamoActivityStore,
    DynamoDbClientProtocol,
    MemoryActivityStore,
)
from nova_file_api.auth import Authenticator
from nova_file_api.cache import LocalTTLCache, SharedRedisCache, TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.jobs import (
    DynamoJobRepository,
    DynamoResource,
    JobPublisher,
    JobRepository,
    JobService,
    MemoryJobPublisher,
    MemoryJobRepository,
    SqsClient,
    SqsJobPublisher,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import (
    ActivityStoreBackend,
    JobsQueueBackend,
    JobsRepositoryBackend,
    Principal,
)
from nova_file_api.transfer import TransferService

_APPLICATION_STATE_NOT_INITIALIZED = "application state is not initialized"
_MSG_JOBS_DYNAMODB_TABLE_REQUIRED = (
    "JOBS_DYNAMODB_TABLE must be configured when "
    "JOBS_REPOSITORY_BACKEND=dynamodb"
)
_MSG_JOBS_SQS_QUEUE_URL_REQUIRED = (
    "JOBS_SQS_QUEUE_URL must be configured when "
    "JOBS_QUEUE_BACKEND=sqs and JOBS_ENABLED=true"
)
_MSG_ACTIVITY_ROLLUPS_TABLE_REQUIRED = (
    "ACTIVITY_ROLLUPS_TABLE must be configured when "
    "ACTIVITY_STORE_BACKEND=dynamodb"
)
_MSG_IDEMPOTENCY_REQUIRES_SHARED_CACHE = (
    "CACHE_REDIS_URL must be configured when IDEMPOTENCY_ENABLED=true"
)
_MSG_S3_CLIENT_REQUIRED = "s3_client must be provided"
_MSG_DYNAMODB_RESOURCE_REQUIRED = (
    "dynamodb_resource must be provided when DynamoDB backends are enabled"
)
_MSG_SQS_CLIENT_REQUIRED = (
    "sqs_client must be provided when JOBS_QUEUE_BACKEND=sqs and "
    "JOBS_ENABLED=true"
)


def _resolve_shared_cache(
    *,
    app: FastAPI,
    settings: Settings,
) -> SharedRedisCache:
    """Resolve the shared cache from providers, state, or fresh settings."""
    shared_cache_provider = getattr(app.state, "_shared_cache_provider", None)
    prebuilt_shared_cache = (
        shared_cache_provider() if callable(shared_cache_provider) else None
    )
    if isinstance(prebuilt_shared_cache, SharedRedisCache):
        return prebuilt_shared_cache

    existing_shared_cache = getattr(app.state, "shared_cache", None)
    if isinstance(existing_shared_cache, SharedRedisCache):
        return existing_shared_cache

    return build_shared_cache(settings=settings)


def _cache_uses_shared_cache(
    cache: object,
    *,
    shared_cache: SharedRedisCache,
) -> bool:
    """Return whether a cache instance is bound to the resolved shared cache."""
    return isinstance(cache, TwoTierCache) and (
        getattr(cache, "_shared", None) is shared_cache
    )


def _idempotency_store_uses_shared_cache(
    store: object,
    *,
    shared_cache: SharedRedisCache,
) -> bool:
    """Return whether a store instance uses the resolved shared cache."""
    return isinstance(store, IdempotencyStore) and (
        getattr(store, "_shared_cache", None) is shared_cache
    )


def initialize_runtime_state(
    app: FastAPI,
    *,
    settings: Settings,
    s3_client: object,
    dynamodb_resource: object | None = None,
    sqs_client: object | None = None,
) -> None:
    """Build and attach runtime singletons to application state.

    Args:
        app: FastAPI application receiving the singletons.
        settings: Resolved runtime settings.
        s3_client: Configured S3 client used by transfer services.
        dynamodb_resource: Optional DynamoDB resource for DynamoDB backends.
        sqs_client: Optional SQS client for queue-backed jobs.

    Returns:
        None.

    Raises:
        ValueError: When runtime prerequisites are not met (missing s3_client,
            JOBS_SQS_QUEUE_URL, JOBS_DYNAMODB_TABLE, etc.).
    """
    if s3_client is None:
        raise ValueError(_MSG_S3_CLIENT_REQUIRED)

    metrics = build_metrics(settings=settings)
    shared_cache = _resolve_shared_cache(app=app, settings=settings)

    cache_provider = getattr(app.state, "_two_tier_cache_provider", None)
    prebuilt_cache = cache_provider() if callable(cache_provider) else None
    existing_cache = getattr(app.state, "cache", None)
    cache: TwoTierCache
    if _cache_uses_shared_cache(prebuilt_cache, shared_cache=shared_cache):
        cache = cast(TwoTierCache, prebuilt_cache)
    elif _cache_uses_shared_cache(existing_cache, shared_cache=shared_cache):
        cache = cast(TwoTierCache, existing_cache)
    else:
        cache = build_two_tier_cache(
            settings=settings,
            metrics=metrics,
            shared_cache=shared_cache,
        )
    job_repository = build_job_repository(
        settings=settings,
        dynamodb_resource=dynamodb_resource,
    )
    job_publisher = build_job_publisher(
        settings=settings,
        sqs_client=sqs_client,
    )
    activity_store = build_activity_store(
        settings=settings,
        dynamodb_resource=dynamodb_resource,
    )

    app.state.settings = settings
    app.state.metrics = metrics
    app.state.shared_cache = shared_cache
    app.state.cache = cache
    app.state.authenticator = build_authenticator(
        settings=settings,
        cache=cache,
    )
    app.state.transfer_service = build_transfer_service(
        settings=settings,
        s3_client=s3_client,
    )
    app.state.job_repository = job_repository
    app.state.job_service = build_job_service(
        job_repository=job_repository,
        job_publisher=job_publisher,
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
    if _idempotency_store_uses_shared_cache(
        prebuilt_idempotency_store,
        shared_cache=shared_cache,
    ):
        idempotency_store = cast(IdempotencyStore, prebuilt_idempotency_store)
    elif _idempotency_store_uses_shared_cache(
        existing_idempotency_store,
        shared_cache=shared_cache,
    ):
        idempotency_store = cast(IdempotencyStore, existing_idempotency_store)
    else:
        idempotency_store = build_idempotency_store(
            settings=settings,
            shared_cache=shared_cache,
        )
    app.state.idempotency_store = idempotency_store


def build_metrics(*, settings: Settings) -> MetricsCollector:
    """Create the metrics collector for the current settings."""
    return MetricsCollector(namespace=settings.metrics_namespace)


def build_shared_cache(*, settings: Settings) -> SharedRedisCache:
    """Create the shared Redis cache wrapper."""
    return SharedRedisCache(
        url=settings.cache_redis_url,
        max_connections=settings.cache_redis_max_connections,
        socket_timeout_seconds=settings.cache_redis_socket_timeout_seconds,
        socket_connect_timeout_seconds=(
            settings.cache_redis_socket_connect_timeout_seconds
        ),
        health_check_interval_seconds=(
            settings.cache_redis_health_check_interval_seconds
        ),
        retry_base_seconds=settings.cache_redis_retry_base_seconds,
        retry_cap_seconds=settings.cache_redis_retry_cap_seconds,
        retry_attempts=settings.cache_redis_retry_attempts,
        decode_responses=settings.cache_redis_decode_responses,
        protocol=settings.cache_redis_protocol,
    )


def build_two_tier_cache(
    *,
    settings: Settings,
    metrics: MetricsCollector,
    shared_cache: SharedRedisCache,
) -> TwoTierCache:
    """Create the two-tier cache used by auth and general cached lookups.

    Args:
        settings: Resolved runtime settings.
        metrics: Metrics collector for cache instrumentation.
        shared_cache: Shared Redis cache for the second tier.

    Returns:
        The configured two-tier cache.
    """
    return TwoTierCache(
        local=LocalTTLCache(
            ttl_seconds=settings.cache_local_ttl_seconds,
            max_entries=settings.cache_local_max_entries,
        ),
        shared=shared_cache,
        shared_ttl_seconds=settings.cache_shared_ttl_seconds,
        key_prefix=settings.cache_key_prefix,
        key_schema_version=settings.cache_key_schema_version,
        metric_incr=metrics.incr,
    )


def build_idempotency_store(
    *,
    settings: Settings,
    shared_cache: SharedRedisCache,
) -> IdempotencyStore:
    """Create the idempotency store.

    Args:
        settings: Resolved runtime settings.
        shared_cache: Shared Redis cache for idempotency entries.

    Returns:
        The configured idempotency store.

    Raises:
        ValueError: When settings.idempotency_enabled is true but
            shared_cache.available is false.
    """
    if settings.idempotency_enabled and not shared_cache.available:
        raise ValueError(_MSG_IDEMPOTENCY_REQUIRES_SHARED_CACHE)
    return IdempotencyStore(
        shared_cache=shared_cache,
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
) -> TransferService:
    """Create the transfer service."""
    return TransferService(settings=settings, s3_client=s3_client)


def build_job_repository(
    *,
    settings: Settings,
    dynamodb_resource: object | None,
) -> JobRepository:
    """Create the configured job repository.

    Args:
        settings: Resolved runtime settings.
        dynamodb_resource: DynamoDB resource when repository backend is
            DynamoDB.

    Returns:
        The configured job repository.

    Raises:
        ValueError: When JOBS_DYNAMODB_TABLE is missing for DynamoDB backend,
            or dynamodb_resource is missing when required.
    """
    if settings.jobs_repository_backend == JobsRepositoryBackend.DYNAMODB:
        jobs_table = (
            settings.jobs_dynamodb_table.strip()
            if settings.jobs_dynamodb_table
            else ""
        )
        if not jobs_table:
            raise ValueError(_MSG_JOBS_DYNAMODB_TABLE_REQUIRED)
        if dynamodb_resource is None:
            raise ValueError(_MSG_DYNAMODB_RESOURCE_REQUIRED)
        return DynamoJobRepository(
            table_name=jobs_table,
            dynamodb_resource=cast(DynamoResource, dynamodb_resource),
        )
    return MemoryJobRepository()


def build_job_publisher(
    *,
    settings: Settings,
    sqs_client: object | None,
) -> JobPublisher:
    """Create the configured job publisher.

    Args:
        settings: Resolved runtime settings.
        sqs_client: SQS client when queue backend is SQS and jobs enabled.

    Returns:
        The configured job publisher.

    Raises:
        ValueError: When JOBS_SQS_QUEUE_URL is missing for SQS backend with
            jobs enabled, or sqs_client is missing when required.
    """
    if settings.jobs_queue_backend == JobsQueueBackend.SQS:
        queue_url = (
            settings.jobs_sqs_queue_url.strip()
            if settings.jobs_sqs_queue_url
            else None
        )
        if settings.jobs_enabled and not queue_url:
            raise ValueError(_MSG_JOBS_SQS_QUEUE_URL_REQUIRED)
        if settings.jobs_enabled and queue_url:
            if sqs_client is None:
                raise ValueError(_MSG_SQS_CLIENT_REQUIRED)
            return SqsJobPublisher(
                queue_url=queue_url,
                sqs_client=cast(SqsClient, sqs_client),
            )
    return MemoryJobPublisher()


def build_job_service(
    *,
    job_repository: JobRepository,
    job_publisher: JobPublisher,
    metrics: MetricsCollector,
) -> JobService:
    """Create the job service.

    Args:
        job_repository: Configured job repository.
        job_publisher: Configured job publisher.
        metrics: Metrics collector for job instrumentation.

    Returns:
        The configured job service.
    """
    return JobService(
        repository=job_repository,
        publisher=job_publisher,
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
            ddb_client=cast(
                DynamoDbClientProtocol,
                _dynamodb_client_from_resource(
                    dynamodb_resource=dynamodb_resource
                ),
            ),
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


def get_shared_cache(request: Request) -> SharedRedisCache:
    """Return the shared cache from app state."""
    shared_cache = getattr(request.app.state, "shared_cache", None)
    if shared_cache is None:
        raise TypeError(_APPLICATION_STATE_NOT_INITIALIZED)
    return cast(SharedRedisCache, shared_cache)


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


def get_job_repository(request: Request) -> JobRepository:
    """Return the job repository from app state."""
    job_repository = getattr(request.app.state, "job_repository", None)
    if job_repository is None:
        raise TypeError(_APPLICATION_STATE_NOT_INITIALIZED)
    return cast(JobRepository, job_repository)


def get_job_service(request: Request) -> JobService:
    """Return the job service from app state."""
    job_service = getattr(request.app.state, "job_service", None)
    if job_service is None:
        raise TypeError(_APPLICATION_STATE_NOT_INITIALIZED)
    return cast(JobService, job_service)


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


def get_request_id(request: Request) -> str | None:
    """Return the request-id value from middleware state."""
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None


async def authenticate_principal(
    *,
    request: Request,
    authenticator: Authenticator,
    session_id: str | None,
) -> Principal:
    """Authenticate the current caller for a request."""
    return await authenticator.authenticate(
        request=request,
        session_id=session_id,
    )


async def get_principal(
    request: Request,
    authenticator: Annotated[Authenticator, Depends(get_authenticator)],
) -> Principal:
    """Authenticate a request that does not rely on a body session id."""
    return await authenticate_principal(
        request=request,
        authenticator=authenticator,
        session_id=None,
    )


SettingsDep = Annotated[Settings, Depends(get_settings)]
MetricsDep = Annotated[MetricsCollector, Depends(get_metrics)]
SharedCacheDep = Annotated[SharedRedisCache, Depends(get_shared_cache)]
TwoTierCacheDep = Annotated[TwoTierCache, Depends(get_two_tier_cache)]
TransferServiceDep = Annotated[TransferService, Depends(get_transfer_service)]
JobRepositoryDep = Annotated[JobRepository, Depends(get_job_repository)]
JobServiceDep = Annotated[JobService, Depends(get_job_service)]
ActivityStoreDep = Annotated[ActivityStore, Depends(get_activity_store)]
IdempotencyStoreDep = Annotated[
    IdempotencyStore,
    Depends(get_idempotency_store),
]
AuthenticatorDep = Annotated[Authenticator, Depends(get_authenticator)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]


def _dynamodb_client_from_resource(*, dynamodb_resource: object) -> object:
    meta = getattr(dynamodb_resource, "meta", None)
    if meta is not None and hasattr(meta, "client"):
        return meta.client
    return dynamodb_resource
