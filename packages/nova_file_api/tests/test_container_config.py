from __future__ import annotations

import pytest
from nova_file_api.config import Settings
from nova_file_api.container import create_container
from nova_file_api.models import (
    ActivityStoreBackend,
    IdempotencyMode,
    JobsQueueBackend,
    JobsRepositoryBackend,
)


def test_create_container_requires_sqs_queue_url_when_jobs_enabled() -> None:
    settings = Settings()
    settings.jobs_enabled = True
    settings.jobs_queue_backend = JobsQueueBackend.SQS
    settings.jobs_sqs_queue_url = None

    with pytest.raises(ValueError, match="JOBS_SQS_QUEUE_URL"):
        create_container(settings=settings)


def test_create_container_allows_missing_sqs_url_when_jobs_disabled() -> None:
    settings = Settings()
    settings.jobs_enabled = False
    settings.jobs_queue_backend = JobsQueueBackend.SQS
    settings.jobs_sqs_queue_url = None

    container = create_container(settings=settings)
    assert container.settings.jobs_enabled is False


def test_create_container_requires_rollup_table_for_dynamodb_backend() -> None:
    settings = Settings()
    settings.activity_store_backend = ActivityStoreBackend.DYNAMODB
    settings.activity_rollups_table = None

    with pytest.raises(ValueError, match="ACTIVITY_ROLLUPS_TABLE"):
        create_container(settings=settings)


def test_create_container_requires_jobs_table_for_dynamodb_repository() -> None:
    settings = Settings()
    settings.jobs_repository_backend = JobsRepositoryBackend.DYNAMODB
    settings.jobs_dynamodb_table = None

    with pytest.raises(ValueError, match="JOBS_DYNAMODB_TABLE"):
        create_container(settings=settings)


def test_settings_require_shared_cache_for_shared_required_idempotency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CACHE_REDIS_URL", raising=False)
    with pytest.raises(ValueError, match="CACHE_REDIS_URL"):
        Settings(
            IDEMPOTENCY_ENABLED=True,
            IDEMPOTENCY_MODE=IdempotencyMode.SHARED_REQUIRED,
        )


def test_settings_require_shared_required_idempotency_in_production() -> None:
    with pytest.raises(ValueError, match="IDEMPOTENCY_MODE"):
        Settings(
            environment="production",
            IDEMPOTENCY_ENABLED=True,
            IDEMPOTENCY_MODE=IdempotencyMode.LOCAL_ONLY,
        )
