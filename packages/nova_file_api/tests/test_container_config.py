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
from pydantic import ValidationError


def _settings() -> Settings:
    """Return environment-isolated default settings for config tests."""
    return Settings.model_validate({})


def _worker_runtime_env(**overrides: object) -> dict[str, object]:
    """Return a valid worker-runtime environment payload for Settings."""
    env: dict[str, object] = {
        "JOBS_ENABLED": True,
        "JOBS_RUNTIME_MODE": "worker",
        "JOBS_QUEUE_BACKEND": JobsQueueBackend.SQS,
        "JOBS_SQS_QUEUE_URL": "https://example.local/queue",
        "JOBS_REPOSITORY_BACKEND": JobsRepositoryBackend.DYNAMODB,
        "JOBS_DYNAMODB_TABLE": "jobs-table",
        "ACTIVITY_STORE_BACKEND": ActivityStoreBackend.DYNAMODB,
        "ACTIVITY_ROLLUPS_TABLE": "activity-table",
    }
    env.update(overrides)
    return env


def test_worker_runtime_requires_dynamodb_jobs_backend() -> None:
    """Worker mode should reject non-DynamoDB job persistence."""
    with pytest.raises(ValidationError, match="JOBS_REPOSITORY_BACKEND"):
        Settings.model_validate(
            _worker_runtime_env(JOBS_REPOSITORY_BACKEND="memory")
        )


def test_worker_runtime_requires_jobs_table_name() -> None:
    """Worker mode should fail fast when the jobs table is missing."""
    with pytest.raises(ValidationError, match="JOBS_DYNAMODB_TABLE"):
        Settings.model_validate(_worker_runtime_env(JOBS_DYNAMODB_TABLE=""))


def test_worker_runtime_requires_dynamodb_activity_backend() -> None:
    """Worker mode should reject non-DynamoDB activity persistence."""
    with pytest.raises(ValidationError, match="ACTIVITY_STORE_BACKEND"):
        Settings.model_validate(
            _worker_runtime_env(ACTIVITY_STORE_BACKEND="memory")
        )


def test_worker_runtime_requires_activity_table_name() -> None:
    """Worker mode should fail fast when the activity table is missing."""
    with pytest.raises(ValidationError, match="ACTIVITY_ROLLUPS_TABLE"):
        Settings.model_validate(_worker_runtime_env(ACTIVITY_ROLLUPS_TABLE=""))


def test_runtime_state_requires_sqs_queue_url_when_jobs_enabled() -> None:
    """Raise ValueError if JOBS_SQS_QUEUE_URL missing with SQS jobs enabled."""
    settings = _settings()
    settings.idempotency_enabled = False
    settings.jobs_enabled = True
    settings.jobs_queue_backend = JobsQueueBackend.SQS
    settings.jobs_sqs_queue_url = None

    with pytest.raises(ValueError, match="JOBS_SQS_QUEUE_URL"):
        initialize_runtime_state(
            FastAPI(), settings=settings, s3_client=object()
        )


def test_initialize_runtime_state_requires_s3_client() -> None:
    """Runtime-state initialization should require an injected S3 client."""
    settings = _settings()
    settings.idempotency_enabled = False
    with pytest.raises(TypeError):
        initialize_runtime_state(  # type: ignore[call-arg]
            FastAPI(),
            settings=settings,
        )


def test_runtime_state_allows_missing_sqs_url_when_jobs_disabled() -> None:
    """Allow missing SQS queue URL when jobs are disabled."""
    settings = _settings()
    settings.idempotency_enabled = False
    settings.jobs_enabled = False
    settings.jobs_queue_backend = JobsQueueBackend.SQS
    settings.jobs_sqs_queue_url = None

    app = FastAPI()
    initialize_runtime_state(app, settings=settings, s3_client=object())
    assert app.state.settings.jobs_enabled is False


def test_runtime_state_requires_rollup_table_for_dynamodb_backend() -> None:
    """Raise ValueError when ACTIVITY_ROLLUPS_TABLE missing for DynamoDB."""
    settings = _settings()
    settings.idempotency_enabled = False
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
    """Raise ValueError when JOBS_DYNAMODB_TABLE missing for DynamoDB."""
    settings = _settings()
    settings.idempotency_enabled = False
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
    settings = _settings()
    settings.idempotency_enabled = False
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
    settings = _settings()
    settings.idempotency_enabled = False
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
    settings = _settings()
    settings.idempotency_enabled = False
    settings.jobs_enabled = True
    settings.jobs_queue_backend = JobsQueueBackend.SQS
    settings.jobs_sqs_queue_url = "https://example.local/queue"
    with pytest.raises(ValueError, match="sqs_client must be provided"):
        initialize_runtime_state(
            FastAPI(), settings=settings, s3_client=object()
        )


def test_runtime_state_requires_shared_cache_when_idempotency_enabled() -> None:
    """Idempotency-enabled startup must require shared-cache configuration."""
    settings = _settings()
    settings.idempotency_enabled = True
    settings.cache_redis_url = None

    with pytest.raises(ValueError, match="CACHE_REDIS_URL"):
        initialize_runtime_state(
            FastAPI(), settings=settings, s3_client=object()
        )
