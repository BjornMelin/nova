from __future__ import annotations

import pytest
from fastapi import FastAPI
from nova_file_api.config import Settings
from nova_file_api.dependencies import initialize_runtime_state
from nova_file_api.models import (
    ActivityStoreBackend,
    JobsQueueBackend,
    JobsRepositoryBackend,
)


def test_runtime_state_requires_sqs_queue_url_when_jobs_enabled() -> None:
    settings = Settings()
    settings.jobs_enabled = True
    settings.jobs_queue_backend = JobsQueueBackend.SQS
    settings.jobs_sqs_queue_url = None

    with pytest.raises(ValueError, match="JOBS_SQS_QUEUE_URL"):
        initialize_runtime_state(
            FastAPI(), settings=settings, s3_client=object()
        )


def test_initialize_runtime_state_requires_s3_client() -> None:
    """Runtime-state initialization should require an injected S3 client."""
    settings = Settings()
    with pytest.raises(TypeError):
        initialize_runtime_state(  # type: ignore[call-arg]
            FastAPI(),
            settings=settings,
        )


def test_runtime_state_allows_missing_sqs_url_when_jobs_disabled() -> None:
    settings = Settings()
    settings.jobs_enabled = False
    settings.jobs_queue_backend = JobsQueueBackend.SQS
    settings.jobs_sqs_queue_url = None

    app = FastAPI()
    initialize_runtime_state(app, settings=settings, s3_client=object())
    assert app.state.settings.jobs_enabled is False


def test_runtime_state_requires_rollup_table_for_dynamodb_backend() -> None:
    settings = Settings()
    settings.activity_store_backend = ActivityStoreBackend.DYNAMODB
    settings.activity_rollups_table = None

    with pytest.raises(ValueError, match="ACTIVITY_ROLLUPS_TABLE"):
        initialize_runtime_state(
            FastAPI(),
            settings=settings,
            s3_client=object(),
            dynamodb_resource=object(),
        )


def test_runtime_state_requires_jobs_table_for_dynamodb_repository() -> None:
    settings = Settings()
    settings.jobs_repository_backend = JobsRepositoryBackend.DYNAMODB
    settings.jobs_dynamodb_table = None

    with pytest.raises(ValueError, match="JOBS_DYNAMODB_TABLE"):
        initialize_runtime_state(
            FastAPI(),
            settings=settings,
            s3_client=object(),
            dynamodb_resource=object(),
        )


def test_runtime_state_requires_dynamodb_resource_for_jobs_backend() -> None:
    """DynamoDB job backends should fail when no resource is injected."""
    settings = Settings()
    settings.jobs_repository_backend = JobsRepositoryBackend.DYNAMODB
    settings.jobs_dynamodb_table = "jobs-table"
    with pytest.raises(
        ValueError,
        match="dynamodb_resource must be provided",
    ):
        initialize_runtime_state(
            FastAPI(), settings=settings, s3_client=object()
        )


def test_runtime_state_requires_dynamodb_resource_for_activity_backend() -> (
    None
):
    """DynamoDB activity backends should fail when no resource is injected."""
    settings = Settings()
    settings.activity_store_backend = ActivityStoreBackend.DYNAMODB
    settings.activity_rollups_table = "activity-rollups"
    with pytest.raises(
        ValueError,
        match="dynamodb_resource must be provided",
    ):
        initialize_runtime_state(
            FastAPI(), settings=settings, s3_client=object()
        )


def test_initialize_runtime_state_requires_sqs_client_when_jobs_enabled() -> (
    None
):
    """SQS job queue should fail when queue URL exists but client is missing."""
    settings = Settings()
    settings.jobs_enabled = True
    settings.jobs_queue_backend = JobsQueueBackend.SQS
    settings.jobs_sqs_queue_url = "https://example.local/queue"
    with pytest.raises(ValueError, match="sqs_client must be provided"):
        initialize_runtime_state(
            FastAPI(), settings=settings, s3_client=object()
        )
