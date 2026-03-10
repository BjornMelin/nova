"""Application dependency container."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nova_file_api.activity import (
    ActivityStore,
    DynamoActivityStore,
    MemoryActivityStore,
)
from nova_file_api.auth import Authenticator
from nova_file_api.cache import (
    LocalTTLCache,
    SharedRedisCache,
    TwoTierCache,
)
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
)
from nova_file_api.transfer import TransferService

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


@dataclass(slots=True)
class AppContainer:
    """Materialized dependencies used by request handlers."""

    settings: Settings
    metrics: MetricsCollector
    cache: TwoTierCache
    shared_cache: SharedRedisCache
    authenticator: Authenticator
    transfer_service: TransferService
    job_repository: JobRepository
    job_service: JobService
    activity_store: ActivityStore
    idempotency_store: IdempotencyStore


def create_container(
    *,
    settings: Settings,
    s3_client: Any,
    dynamodb_resource: Any | None = None,
    sqs_client: Any | None = None,
) -> AppContainer:
    """
    Build an AppContainer populated with application dependencies derived from settings and provided clients.
    
    Validates required external clients/resources and constructs metrics, caching layers, idempotency store, authenticator, transfer service, job repository/publisher, job service, and activity store according to settings.
    
    Parameters:
        settings (Settings): Application settings that drive which backends are created and their configuration.
        s3_client (Any): S3 client instance; required for the transfer service.
        dynamodb_resource (Any | None): Optional DynamoDB resource or client; required when a DynamoDB-backed repository or activity store is selected.
        sqs_client (Any | None): Optional SQS client; required when SQS is used as the jobs queue backend and a queue URL is configured.
    
    Returns:
        AppContainer: Container with instantiated components (settings, metrics, cache, shared_cache, authenticator, transfer_service, job_repository, job_service, activity_store, idempotency_store).
    
    Raises:
        ValueError: If `s3_client` is None.
        ValueError: If a DynamoDB backend is selected but `dynamodb_resource` is None or required table names are missing.
        ValueError: If jobs queue backend is SQS and jobs are enabled but queue URL is missing.
        ValueError: If SQS is required (queue URL provided) but `sqs_client` is None.
    """
    if s3_client is None:
        raise ValueError(_MSG_S3_CLIENT_REQUIRED)
    metrics = MetricsCollector(namespace=settings.metrics_namespace)
    local_cache = LocalTTLCache(
        ttl_seconds=settings.cache_local_ttl_seconds,
        max_entries=settings.cache_local_max_entries,
    )
    shared_cache = SharedRedisCache(
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
    cache = TwoTierCache(
        local=local_cache,
        shared=shared_cache,
        shared_ttl_seconds=settings.cache_shared_ttl_seconds,
        key_prefix=settings.cache_key_prefix,
        key_schema_version=settings.cache_key_schema_version,
        metric_incr=metrics.incr,
    )
    idempotency_store = IdempotencyStore(
        cache=cache,
        enabled=settings.idempotency_enabled,
        ttl_seconds=settings.idempotency_ttl_seconds,
    )

    authenticator = Authenticator(settings=settings, cache=cache)
    transfer_service = TransferService(settings=settings, s3_client=s3_client)

    job_repository: JobRepository
    if settings.jobs_repository_backend == JobsRepositoryBackend.DYNAMODB:
        if not settings.jobs_dynamodb_table:
            raise ValueError(_MSG_JOBS_DYNAMODB_TABLE_REQUIRED)
        if dynamodb_resource is None:
            raise ValueError(_MSG_DYNAMODB_RESOURCE_REQUIRED)
        job_repository = DynamoJobRepository(
            table_name=settings.jobs_dynamodb_table,
            dynamodb_resource=dynamodb_resource,
        )
    else:
        job_repository = MemoryJobRepository()
    publisher: JobPublisher
    if settings.jobs_queue_backend == JobsQueueBackend.SQS:
        if settings.jobs_enabled and not settings.jobs_sqs_queue_url:
            raise ValueError(_MSG_JOBS_SQS_QUEUE_URL_REQUIRED)
        if settings.jobs_sqs_queue_url:
            if sqs_client is None:
                raise ValueError(_MSG_SQS_CLIENT_REQUIRED)
            publisher = SqsJobPublisher(
                queue_url=settings.jobs_sqs_queue_url,
                sqs_client=sqs_client,
            )
        else:
            publisher = MemoryJobPublisher()
    else:
        publisher = MemoryJobPublisher()
    job_service = JobService(
        repository=job_repository,
        publisher=publisher,
        metrics=metrics,
    )

    activity_store: ActivityStore
    if settings.activity_store_backend == ActivityStoreBackend.DYNAMODB:
        if not settings.activity_rollups_table:
            raise ValueError(_MSG_ACTIVITY_ROLLUPS_TABLE_REQUIRED)
        if dynamodb_resource is None:
            raise ValueError(_MSG_DYNAMODB_RESOURCE_REQUIRED)
        ddb_client = _dynamodb_client_from_resource(
            dynamodb_resource=dynamodb_resource
        )
        activity_store = DynamoActivityStore(
            table_name=settings.activity_rollups_table,
            ddb_client=ddb_client,
        )
    else:
        activity_store = MemoryActivityStore()

    return AppContainer(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared_cache,
        authenticator=authenticator,
        transfer_service=transfer_service,
        job_repository=job_repository,
        job_service=job_service,
        activity_store=activity_store,
        idempotency_store=idempotency_store,
    )


def _dynamodb_client_from_resource(*, dynamodb_resource: Any) -> Any:
    """
    Extracts a DynamoDB client from a provided resource if available.
    
    Parameters:
        dynamodb_resource (Any): A Boto3 DynamoDB resource or client-like object. If the object exposes a `meta.client` attribute, that client will be used.
    
    Returns:
        Any: The DynamoDB client found at `dynamodb_resource.meta.client`, or the original `dynamodb_resource` if no such client exists.
    """
    meta = getattr(dynamodb_resource, "meta", None)
    if meta is not None and hasattr(meta, "client"):
        return meta.client
    return dynamodb_resource
