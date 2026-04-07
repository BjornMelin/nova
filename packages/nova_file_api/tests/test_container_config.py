from __future__ import annotations

from typing import Any, cast

import pytest
from botocore.config import Config
from fastapi import FastAPI

from nova_file_api.app import create_app
from nova_file_api.config import Settings
from nova_file_api.dependencies import (
    build_idempotency_store,
    initialize_runtime_state,
)
from nova_file_api.models import ActivityStoreBackend

from .support.dynamodb import MemoryDynamoResource


class _AsyncContextValue:
    def __init__(self, value: object) -> None:
        self._value = value

    async def __aenter__(self) -> object:
        return self._value

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> bool:
        del exc_type, exc, tb
        return False


class _RecordingSession:
    def __init__(self) -> None:
        self.client_calls: list[tuple[str, Config | None]] = []
        self.resource_calls: list[tuple[str, Config | None]] = []

    def client(
        self, service_name: str, *, config: Config | None = None
    ) -> _AsyncContextValue:
        self.client_calls.append((service_name, config))
        return _AsyncContextValue(object())

    def resource(
        self, service_name: str, *, config: Config | None = None
    ) -> _AsyncContextValue:
        self.resource_calls.append((service_name, config))
        return _AsyncContextValue(object())


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


def test_create_app_enables_strict_content_type() -> None:
    """The public API should keep strict JSON content-type enforcement on."""
    app = create_app(settings=_settings())

    assert app.router.strict_content_type is True


@pytest.mark.anyio
async def test_runtime_app_lifespan_uses_shared_aws_client_configs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import nova_file_api.app as app_module

    session = _RecordingSession()

    def _fake_initialize_runtime_state(
        app: FastAPI,
        *,
        settings: Settings,
        s3_client: object,
        accelerate_s3_client: object | None = None,
        dynamodb_resource: object | None = None,
        stepfunctions_client: object | None = None,
        appconfig_client: object | None = None,
    ) -> None:
        del (
            app,
            settings,
            s3_client,
            accelerate_s3_client,
            dynamodb_resource,
            stepfunctions_client,
            appconfig_client,
        )

    monkeypatch.setattr(
        app_module.aioboto3,
        "Session",
        lambda: session,
    )
    monkeypatch.setattr(
        app_module,
        "initialize_runtime_state",
        _fake_initialize_runtime_state,
    )

    app = create_app(
        settings=Settings.model_validate(
            {
                "EXPORTS_ENABLED": True,
                "EXPORTS_DYNAMODB_TABLE": "exports-table",
                "EXPORT_WORKFLOW_STATE_MACHINE_ARN": (
                    "arn:aws:states:us-east-1:123456789012:stateMachine:nova"
                ),
                "FILE_TRANSFER_ENABLED": False,
                "IDEMPOTENCY_ENABLED": False,
                "FILE_TRANSFER_POLICY_APPCONFIG_APPLICATION": "app",
                "FILE_TRANSFER_POLICY_APPCONFIG_ENVIRONMENT": "env",
                "FILE_TRANSFER_POLICY_APPCONFIG_PROFILE": "profile",
            }
        )
    )

    async with app.router.lifespan_context(app):
        pass

    assert [name for name, _ in session.client_calls] == [
        "s3",
        "s3",
        "stepfunctions",
        "appconfigdata",
    ]
    assert [name for name, _ in session.resource_calls] == ["dynamodb"]
    assert isinstance(session.client_calls[0][1], Config)
    assert session.client_calls[0][1].s3 == {"use_accelerate_endpoint": False}
    assert isinstance(session.client_calls[1][1], Config)
    assert session.client_calls[1][1].s3 == {"use_accelerate_endpoint": True}
    assert isinstance(session.client_calls[2][1], Config)
    assert session.client_calls[2][1].s3 is None
    assert isinstance(session.client_calls[3][1], Config)
    assert session.client_calls[3][1].s3 is None
    assert isinstance(session.resource_calls[0][1], Config)
