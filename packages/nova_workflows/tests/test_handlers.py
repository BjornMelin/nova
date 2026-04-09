from __future__ import annotations

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from botocore.config import Config

from nova_file_api.workflow_facade import (
    ExportCopyPoisonMessage,
    ExportCopyTaskMessage,
)
from nova_workflows import handlers

from .conftest import RecordingSession


class _FakeLargeCopyService:
    def __init__(self) -> None:
        self.messages: list[tuple[str, ExportCopyTaskMessage]] | None = None
        self.invalid_terminalizable: list[bool] = []
        self.observed_lag: list[int | None] = []
        self.poison_messages: list[ExportCopyPoisonMessage] = []

    async def process_message_batch(
        self,
        *,
        messages: list[tuple[str, ExportCopyTaskMessage]],
    ) -> list[str]:
        self.messages = messages
        return ["good-message"] if messages else []

    def observe_message_lag(self, *, sent_timestamp_ms: int | None) -> None:
        self.observed_lag.append(sent_timestamp_ms)

    def record_invalid_message(self, *, terminalizable: bool) -> None:
        self.invalid_terminalizable.append(terminalizable)

    async def terminalize_poison_message(
        self,
        *,
        poison: ExportCopyPoisonMessage,
    ) -> None:
        self.poison_messages.append(poison)


@pytest.mark.anyio
async def test_export_copy_worker_terminalizes_invalid_messages_with_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _FakeLargeCopyService()

    @asynccontextmanager
    async def fake_workflow_services(*, settings: object):
        del settings
        yield SimpleNamespace(large_copy_service=service)

    monkeypatch.setattr(handlers, "WorkflowSettings", lambda: object())
    monkeypatch.setattr(handlers, "workflow_services", fake_workflow_services)
    result = await handlers._export_copy_worker(
        event={
            "Records": [
                {
                    "messageId": "bad-message",
                    "body": "{not-json}",
                    "attributes": {"SentTimestamp": "100"},
                    "messageAttributes": {
                        "export_id": {"stringValue": "export-1"},
                        "part_number": {"stringValue": "1"},
                        "upload_id": {"stringValue": "upload-1"},
                    },
                },
                {
                    "messageId": "good-message",
                    "body": json.dumps(
                        {
                            "end_byte": 9,
                            "export_id": "export-1",
                            "export_key": "exports/scope-1/export-1/file.csv",
                            "part_number": 1,
                            "source_key": "uploads/scope-1/file.csv",
                            "start_byte": 0,
                            "upload_id": "upload-1",
                        }
                    ),
                    "attributes": {"SentTimestamp": "200"},
                },
            ]
        }
    )

    assert service.messages == [
        (
            "good-message",
            ExportCopyTaskMessage(
                export_id="export-1",
                source_key="uploads/scope-1/file.csv",
                export_key="exports/scope-1/export-1/file.csv",
                upload_id="upload-1",
                part_number=1,
                start_byte=0,
                end_byte=9,
            ),
        )
    ]
    assert service.invalid_terminalizable == [True]
    assert service.observed_lag == [200, 100]
    assert service.poison_messages == [
        ExportCopyPoisonMessage(
            export_id="export-1",
            part_number=1,
            upload_id="upload-1",
        )
    ]
    assert result == {"batchItemFailures": [{"itemIdentifier": "good-message"}]}


@pytest.mark.anyio
async def test_export_copy_worker_counts_unresolved_invalid_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _FakeLargeCopyService()

    @asynccontextmanager
    async def fake_workflow_services(*, settings: object):
        del settings
        yield SimpleNamespace(large_copy_service=service)

    monkeypatch.setattr(handlers, "WorkflowSettings", lambda: object())
    monkeypatch.setattr(handlers, "workflow_services", fake_workflow_services)
    result = await handlers._export_copy_worker(
        event={
            "Records": [
                {
                    "messageId": "bad-message",
                    "body": "{not-json}",
                    "attributes": {"SentTimestamp": "300"},
                }
            ]
        }
    )

    assert service.messages == []
    assert service.invalid_terminalizable == [False]
    assert service.observed_lag == [300]
    assert service.poison_messages == []
    assert result == {"batchItemFailures": [{"itemIdentifier": "bad-message"}]}


@pytest.mark.anyio
async def test_export_copy_worker_treats_invalid_coordinates_as_poison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _FakeLargeCopyService()

    @asynccontextmanager
    async def fake_workflow_services(*, settings: object):
        del settings
        yield SimpleNamespace(large_copy_service=service)

    monkeypatch.setattr(handlers, "WorkflowSettings", lambda: object())
    monkeypatch.setattr(handlers, "workflow_services", fake_workflow_services)
    result = await handlers._export_copy_worker(
        event={
            "Records": [
                {
                    "messageId": "poison-message",
                    "body": json.dumps(
                        {
                            "end_byte": 8,
                            "export_id": "export-1",
                            "export_key": "exports/scope-1/export-1/file.csv",
                            "part_number": 0,
                            "source_key": "uploads/scope-1/file.csv",
                            "start_byte": 9,
                            "upload_id": "upload-1",
                        }
                    ),
                    "attributes": {"SentTimestamp": "400"},
                    "messageAttributes": {
                        "export_id": {"stringValue": "export-1"},
                        "part_number": {"stringValue": "1"},
                        "upload_id": {"stringValue": "upload-1"},
                    },
                }
            ]
        }
    )

    assert service.messages == []
    assert service.invalid_terminalizable == [True]
    assert service.observed_lag == [400]
    assert service.poison_messages == [
        ExportCopyPoisonMessage(
            export_id="export-1",
            part_number=1,
            upload_id="upload-1",
        )
    ]
    assert result == {"batchItemFailures": []}


@pytest.mark.anyio
async def test_reconcile_transfer_state_uses_shared_aws_client_configs(
    monkeypatch: pytest.MonkeyPatch,
    recording_session: RecordingSession,
) -> None:
    captured: dict[str, object] = {}
    upload_session_repo_kwargs: dict[str, object] = {}
    transfer_usage_repo_kwargs: dict[str, object] = {}
    upload_session_repository = object()
    transfer_usage_repository = object()
    settings = handlers.WorkflowSettings.model_validate(
        {
            "EXPORTS_ENABLED": False,
            "FILE_TRANSFER_BUCKET": "workflow-bucket",
            "FILE_TRANSFER_USE_ACCELERATE_ENDPOINT": True,
            "FILE_TRANSFER_UPLOAD_SESSIONS_TABLE": "upload-sessions",
            "FILE_TRANSFER_USAGE_TABLE": "usage-table",
        }
    )

    class _FakeResult:
        def as_dict(self) -> dict[str, str]:
            return {"status": "ok"}

    class _FakeReconciliationService:
        def __init__(
            self,
            *,
            config: object,
            s3_client: object,
            upload_session_repository: object,
            transfer_usage_repository: object,
        ) -> None:
            captured["config"] = config
            captured["s3_client"] = s3_client
            captured["upload_session_repository"] = upload_session_repository
            captured["transfer_usage_repository"] = transfer_usage_repository

        async def reconcile(self) -> _FakeResult:
            return _FakeResult()

    monkeypatch.setattr(
        handlers.aioboto3,
        "Session",
        lambda: recording_session,
    )
    monkeypatch.setattr(
        handlers,
        "WorkflowSettings",
        lambda: settings,
    )
    monkeypatch.setattr(
        handlers,
        "build_upload_session_repository",
        lambda **kwargs: (
            upload_session_repo_kwargs.update(kwargs)
            or upload_session_repository
        ),
    )
    monkeypatch.setattr(
        handlers,
        "build_transfer_usage_window_repository",
        lambda **kwargs: (
            transfer_usage_repo_kwargs.update(kwargs)
            or transfer_usage_repository
        ),
    )
    monkeypatch.setattr(
        handlers,
        "TransferReconciliationService",
        _FakeReconciliationService,
    )

    result = await handlers._reconcile_transfer_state(event={})

    assert result == {"status": "ok"}
    assert [name for name, _ in recording_session.client_calls] == ["s3"]
    assert [name for name, _ in recording_session.resource_calls] == [
        "dynamodb"
    ]
    assert isinstance(recording_session.client_calls[0][1], Config)
    assert recording_session.client_calls[0][1].s3 == {
        "use_accelerate_endpoint": True
    }
    assert isinstance(recording_session.resource_calls[0][1], Config)
    assert recording_session.resource_calls[0][1].s3 is None
    assert captured["s3_client"] is not None
    assert captured["upload_session_repository"] is upload_session_repository
    assert upload_session_repo_kwargs["table_name"] == "upload-sessions"
    assert upload_session_repo_kwargs["enabled"] is True
    assert captured["transfer_usage_repository"] is transfer_usage_repository
    assert transfer_usage_repo_kwargs["table_name"] == "usage-table"
    assert transfer_usage_repo_kwargs["enabled"] is True
    assert (
        upload_session_repo_kwargs["dynamodb_resource"]
        is transfer_usage_repo_kwargs["dynamodb_resource"]
    )
    assert captured["config"] == handlers.TransferReconciliationConfig(
        bucket="workflow-bucket",
        upload_prefix=settings.file_transfer_upload_prefix,
        export_prefix=settings.file_transfer_export_prefix,
        stale_multipart_cleanup_age_seconds=(
            settings.file_transfer_stale_multipart_cleanup_age_seconds
        ),
        session_scan_limit=settings.file_transfer_reconciliation_scan_limit,
    )
