from __future__ import annotations

from typing import Any, cast

import pytest
from fastapi import FastAPI

from nova_file_api.config import Settings
from nova_file_api.dependencies import (
    build_idempotency_store,
    initialize_runtime_state,
)
from nova_file_api.models import ActivityStoreBackend

from .support.dynamodb import MemoryDynamoResource


def _settings() -> Settings:
    """Return environment-isolated default settings for config tests."""
    return Settings.model_validate(
        {
            "EXPORTS_ENABLED": False,
            "IDEMPOTENCY_ENABLED": False,
            "FILE_TRANSFER_ENABLED": False,
            "IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency",
        }
    )


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


@pytest.mark.parametrize(
    ("overrides", "runtime_kwargs", "expected_match"),
    [
        pytest.param(
            {
                "file_transfer_enabled": True,
                "file_transfer_upload_sessions_table": None,
            },
            {},
            "FILE_TRANSFER_UPLOAD_SESSIONS_TABLE",
            id="file-transfer-enabled-requires-session-table",
        ),
        pytest.param(
            {
                "idempotency_enabled": False,
                "exports_enabled": True,
                "exports_dynamodb_table": None,
            },
            {"dynamodb_resource": object()},
            "EXPORTS_DYNAMODB_TABLE",
            id="exports-enabled-requires-table",
        ),
        pytest.param(
            {
                "idempotency_enabled": False,
                "exports_enabled": True,
                "exports_dynamodb_table": "exports-table",
            },
            {},
            "dynamodb_resource must be provided",
            id="exports-enabled-requires-resource",
        ),
        pytest.param(
            {
                "idempotency_enabled": False,
                "exports_enabled": True,
                "exports_dynamodb_table": "exports-table",
            },
            {"dynamodb_resource": object()},
            "EXPORT_WORKFLOW_STATE_MACHINE_ARN",
            id="exports-enabled-requires-state-machine",
        ),
        pytest.param(
            {
                "idempotency_enabled": False,
                "exports_enabled": True,
                "exports_dynamodb_table": "exports-table",
                "export_workflow_state_machine_arn": (
                    "arn:aws:states:us-east-1:123456789012:stateMachine:nova"
                ),
            },
            {"dynamodb_resource": object()},
            "stepfunctions_client must be provided",
            id="exports-enabled-requires-stepfunctions-client",
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
                "activity_store_backend": ActivityStoreBackend.DYNAMODB,
                "activity_rollups_table": "activity-rollups",
            },
            {},
            "dynamodb_resource must be provided",
            id="activity-dynamodb-requires-resource",
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
    """Fail fast when runtime dependencies required by settings are absent."""
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


def test_exports_disabled_allow_missing_workflow_runtime() -> None:
    """Allow missing export workflow wiring when exports are disabled."""
    settings = _settings()
    settings.idempotency_enabled = False
    settings.exports_enabled = False

    app = FastAPI()
    initialize_runtime_state(app, settings=settings, s3_client=object())
    assert app.state.settings.exports_enabled is False
