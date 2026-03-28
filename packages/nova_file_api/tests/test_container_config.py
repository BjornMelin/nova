from __future__ import annotations

from typing import Any, cast

import pytest
from fastapi import FastAPI
from nova_file_api.config import Settings
from nova_file_api.dependencies import (
    build_idempotency_store,
    initialize_runtime_state,
)
from nova_file_api.models import (
    ActivityStoreBackend,
    JobsQueueBackend,
    JobsRepositoryBackend,
)
from pydantic import ValidationError

from .support.dynamodb import MemoryDynamoResource


def _settings() -> Settings:
    """Return environment-isolated default settings for config tests."""
    return Settings.model_validate(
        {
            "IDEMPOTENCY_ENABLED": False,
            "IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency",
        }
    )


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


def test_settings_accept_env_style_keys() -> None:
    """Settings should accept explicit env-var keys for validation."""
    settings = Settings.model_validate(
        {
            "APP_NAME": "runtime-env-app",
            "FILE_TRANSFER_BUCKET": "env-bucket",
            "IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency",
        }
    )

    assert settings.app_name == "runtime-env-app"
    assert settings.file_transfer_bucket == "env-bucket"
    assert settings.idempotency_dynamodb_table == "test-idempotency"


def test_settings_accept_field_name_keys() -> None:
    """Settings should also accept canonical snake_case field names."""
    settings = Settings.model_validate(
        {
            "app_name": "field-name-app",
            "file_transfer_bucket": "field-bucket",
            "idempotency_enabled": False,
            "idempotency_dynamodb_table": "test-idempotency",
        }
    )

    assert settings.app_name == "field-name-app"
    assert settings.file_transfer_bucket == "field-bucket"
    assert settings.idempotency_dynamodb_table == "test-idempotency"


def test_settings_model_dump_uses_field_names() -> None:
    """Settings serialization should keep snake_case field names."""
    settings = Settings.model_validate(
        {
            "APP_NAME": "serialized-app",
            "FILE_TRANSFER_BUCKET": "serialized-bucket",
            "IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency",
        }
    )

    payload = settings.model_dump()

    assert payload["app_name"] == "serialized-app"
    assert payload["file_transfer_bucket"] == "serialized-bucket"
    assert payload["idempotency_dynamodb_table"] == "test-idempotency"
    assert "APP_NAME" not in payload
    assert "FILE_TRANSFER_BUCKET" not in payload


def test_build_idempotency_store_strips_table_name() -> None:
    """Configured idempotency table names should be trimmed before use."""
    settings = Settings.model_validate(
        {
            "IDEMPOTENCY_ENABLED": True,
            "IDEMPOTENCY_DYNAMODB_TABLE": "  test-idempotency  ",
        }
    )

    store = build_idempotency_store(
        settings=settings,
        dynamodb_resource=MemoryDynamoResource(),
    )

    assert store.table_name == "test-idempotency"


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


def test_step_functions_backend_requires_state_machine_arn() -> None:
    """Step Functions mode should fail fast when the ARN is missing."""
    with pytest.raises(
        ValidationError, match="JOBS_STEP_FUNCTIONS_STATE_MACHINE_ARN"
    ):
        Settings.model_validate(
            {
                "IDEMPOTENCY_ENABLED": False,
                "JOBS_ENABLED": True,
                "JOBS_QUEUE_BACKEND": JobsQueueBackend.STEP_FUNCTIONS,
            }
        )


@pytest.mark.parametrize(
    ("overrides", "runtime_kwargs", "expected_match"),
    [
        pytest.param(
            {
                "idempotency_enabled": False,
                "jobs_enabled": True,
                "jobs_queue_backend": JobsQueueBackend.SQS,
                "jobs_sqs_queue_url": None,
            },
            {},
            "JOBS_SQS_QUEUE_URL",
            id="jobs-enabled-requires-queue-url",
        ),
        pytest.param(
            {
                "idempotency_enabled": False,
                "activity_store_backend": ActivityStoreBackend.DYNAMODB,
                "activity_rollups_table": None,
            },
            {"dynamodb_resource": object()},
            "ACTIVITY_ROLLUPS_TABLE",
            id="activity-dynamodb-requires-rollups-table",
        ),
        pytest.param(
            {
                "idempotency_enabled": False,
                "jobs_repository_backend": JobsRepositoryBackend.DYNAMODB,
                "jobs_dynamodb_table": None,
            },
            {"dynamodb_resource": object()},
            "JOBS_DYNAMODB_TABLE",
            id="jobs-dynamodb-requires-table",
        ),
        pytest.param(
            {
                "idempotency_enabled": False,
                "jobs_repository_backend": JobsRepositoryBackend.DYNAMODB,
                "jobs_dynamodb_table": "jobs-table",
            },
            {},
            "dynamodb_resource must be provided",
            id="jobs-dynamodb-requires-resource",
        ),
        pytest.param(
            {
                "idempotency_enabled": False,
                "activity_store_backend": ActivityStoreBackend.DYNAMODB,
                "activity_rollups_table": "activity-rollups",
            },
            {},
            "dynamodb_resource must be provided",
            id="activity-dynamodb-requires-resource",
        ),
        pytest.param(
            {
                "idempotency_enabled": False,
                "jobs_enabled": True,
                "jobs_queue_backend": JobsQueueBackend.SQS,
                "jobs_sqs_queue_url": "https://example.local/queue",
            },
            {},
            "sqs_client must be provided",
            id="sqs-enabled-requires-client",
        ),
        pytest.param(
            {
                "idempotency_enabled": True,
                "idempotency_dynamodb_table": "test-idempotency",
            },
            {},
            "dynamodb_resource must be provided",
            id="idempotency-requires-resource",
        ),
    ],
)
@pytest.mark.runtime_gate
def test_runtime_state_validates_required_dependencies(
    overrides: dict[str, object],
    runtime_kwargs: dict[str, object],
    expected_match: str,
) -> None:
    """Runtime-state initialization should fail fast on missing dependencies."""
    settings = _settings()
    for field_name, value in overrides.items():
        setattr(settings, field_name, value)

    with pytest.raises(ValueError, match=expected_match):
        initialize_runtime_state(
            FastAPI(),
            settings=settings,
            s3_client=object(),
            **runtime_kwargs,
        )


def test_initialize_runtime_state_requires_s3_client() -> None:
    """Runtime-state initialization should require an injected S3 client."""
    settings = _settings()
    settings.idempotency_enabled = False
    with pytest.raises(TypeError):
        cast(Any, initialize_runtime_state)(
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
