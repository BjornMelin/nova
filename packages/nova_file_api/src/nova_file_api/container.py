"""Application dependency container."""

from __future__ import annotations

from dataclasses import dataclass

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


def create_container(*, settings: Settings) -> AppContainer:
    """Build dependency container from settings."""
    metrics = MetricsCollector(namespace=settings.metrics_namespace)
    local_cache = LocalTTLCache(
        ttl_seconds=settings.cache_local_ttl_seconds,
        max_entries=settings.cache_local_max_entries,
    )
    shared_cache = SharedRedisCache(url=settings.cache_shared_backend_url)
    cache = TwoTierCache(
        local=local_cache,
        shared=shared_cache,
        shared_ttl_seconds=settings.cache_shared_ttl_seconds,
        metric_incr=metrics.incr,
    )
    idempotency_store = IdempotencyStore(
        cache=cache,
        enabled=settings.idempotency_enabled,
        ttl_seconds=settings.idempotency_ttl_seconds,
    )

    authenticator = Authenticator(settings=settings, cache=cache)
    transfer_service = TransferService(settings=settings)

    job_repository: JobRepository
    if settings.jobs_repository_backend == JobsRepositoryBackend.DYNAMODB:
        if not settings.jobs_dynamodb_table:
            raise ValueError(
                "JOBS_DYNAMODB_TABLE must be configured when "
                "JOBS_REPOSITORY_BACKEND=dynamodb"
            )
        job_repository = DynamoJobRepository(
            table_name=settings.jobs_dynamodb_table
        )
    else:
        job_repository = MemoryJobRepository()
    publisher: JobPublisher
    if settings.jobs_queue_backend == JobsQueueBackend.SQS:
        if settings.jobs_enabled and not settings.jobs_sqs_queue_url:
            raise ValueError(
                "JOBS_SQS_QUEUE_URL must be configured when "
                "JOBS_QUEUE_BACKEND=sqs and JOBS_ENABLED=true"
            )
        if settings.jobs_sqs_queue_url:
            publisher = SqsJobPublisher(
                queue_url=settings.jobs_sqs_queue_url,
                retry_mode=settings.jobs_sqs_retry_mode,
                retry_total_max_attempts=settings.jobs_sqs_retry_total_max_attempts,
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
            raise ValueError(
                "ACTIVITY_ROLLUPS_TABLE must be configured when "
                "ACTIVITY_STORE_BACKEND=dynamodb"
            )
        activity_store = DynamoActivityStore(
            table_name=settings.activity_rollups_table
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
