"""FastAPI dependency helpers and runtime state assembly."""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastapi import Depends, FastAPI, Request

from nova_file_api.activity import (
    ActivityStore,
    DynamoActivityStore,
    MemoryActivityStore,
)
from nova_file_api.auth import Authenticator
from nova_file_api.cache import LocalTTLCache, SharedRedisCache, TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.jobs import (
    DynamoJobRepository,
    JobPublisher,
    JobRepository,
    JobService,
    MemoryJobPublisher,
    MemoryJobRepository,
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
_MSG_S3_CLIENT_REQUIRED = "s3_client must be provided"
_MSG_DYNAMODB_RESOURCE_REQUIRED = (
    "dynamodb_resource must be provided when DynamoDB backends are enabled"
)
_MSG_SQS_CLIENT_REQUIRED = (
    "sqs_client must be provided when JOBS_QUEUE_BACKEND=sqs and "
    "JOBS_ENABLED=true"
)


def initialize_runtime_state(
    app: FastAPI,
    *,
    settings: Settings,
    s3_client: Any,
    dynamodb_resource: Any | None = None,
    sqs_client: Any | None = None,
) -> None:
    """Build and attach runtime singletons to application state.

    Args:
        app: FastAPI application receiving the singletons.
        settings: Resolved runtime settings.
        s3_client: Configured S3 client used by transfer services.
        dynamodb_resource: Optional DynamoDB resource for DynamoDB backends.
        sqs_client: Optional SQS client for queue-backed jobs.
    """
    if s3_client is None:
        raise ValueError(_MSG_S3_CLIENT_REQUIRED)

    metrics = build_metrics(settings=settings)
    shared_cache = build_shared_cache(settings=settings)
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
    app.state.idempotency_store = build_idempotency_store(
        settings=settings,
        cache=cache,
    )


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
    """Create the two-tier cache used by auth and idempotency."""
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
    cache: TwoTierCache,
) -> IdempotencyStore:
    """Create the idempotency store."""
    return IdempotencyStore(
        cache=cache,
        enabled=settings.idempotency_enabled,
        ttl_seconds=settings.idempotency_ttl_seconds,
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
    s3_client: Any,
) -> TransferService:
    """Create the transfer service."""
    return TransferService(settings=settings, s3_client=s3_client)


def build_job_repository(
    *,
    settings: Settings,
    dynamodb_resource: Any | None,
) -> JobRepository:
    """Create the configured job repository."""
    if settings.jobs_repository_backend == JobsRepositoryBackend.DYNAMODB:
        if not settings.jobs_dynamodb_table:
            raise ValueError(_MSG_JOBS_DYNAMODB_TABLE_REQUIRED)
        if dynamodb_resource is None:
            raise ValueError(_MSG_DYNAMODB_RESOURCE_REQUIRED)
        return DynamoJobRepository(
            table_name=settings.jobs_dynamodb_table,
            dynamodb_resource=dynamodb_resource,
        )
    return MemoryJobRepository()


def build_job_publisher(
    *,
    settings: Settings,
    sqs_client: Any | None,
) -> JobPublisher:
    """Create the configured job publisher."""
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
            return SqsJobPublisher(queue_url=queue_url, sqs_client=sqs_client)
    return MemoryJobPublisher()


def build_job_service(
    *,
    job_repository: JobRepository,
    job_publisher: JobPublisher,
    metrics: MetricsCollector,
) -> JobService:
    """Create the job service."""
    return JobService(
        repository=job_repository,
        publisher=job_publisher,
        metrics=metrics,
    )


def build_activity_store(
    *,
    settings: Settings,
    dynamodb_resource: Any | None,
) -> ActivityStore:
    """Create the configured activity store."""
    if settings.activity_store_backend == ActivityStoreBackend.DYNAMODB:
        if not settings.activity_rollups_table:
            raise ValueError(_MSG_ACTIVITY_ROLLUPS_TABLE_REQUIRED)
        if dynamodb_resource is None:
            raise ValueError(_MSG_DYNAMODB_RESOURCE_REQUIRED)
        return DynamoActivityStore(
            table_name=settings.activity_rollups_table,
            ddb_client=_dynamodb_client_from_resource(
                dynamodb_resource=dynamodb_resource
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


def _dynamodb_client_from_resource(*, dynamodb_resource: Any) -> Any:
    meta = getattr(dynamodb_resource, "meta", None)
    if meta is not None and hasattr(meta, "client"):
        return meta.client
    return dynamodb_resource
