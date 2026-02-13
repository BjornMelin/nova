from __future__ import annotations

import pytest
from nova_file_api.config import Settings
from nova_file_api.container import create_container
from nova_file_api.models import (
    ActivityStoreBackend,
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
