from __future__ import annotations

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from botocore.config import Config

from nova_file_api.workflow_facade import ExportCopyTaskMessage
from nova_workflows import handlers


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


class _FakeLargeCopyService:
    def __init__(self) -> None:
        self.messages: list[tuple[str, ExportCopyTaskMessage]] | None = None

    async def process_message_batch(
        self,
        *,
        messages: list[tuple[str, ExportCopyTaskMessage]],
    ) -> list[str]:
        self.messages = messages
        return ["good-message"]


@pytest.mark.anyio
async def test_export_copy_worker_marks_invalid_messages_as_failures(
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
                {"messageId": "bad-message", "body": "{not-json}"},
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
    assert result == {
        "batchItemFailures": [
            {"itemIdentifier": "bad-message"},
            {"itemIdentifier": "good-message"},
        ]
    }


@pytest.mark.anyio
async def test_reconcile_transfer_state_uses_shared_aws_client_configs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _RecordingSession()
    captured: dict[str, object] = {}
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

    monkeypatch.setattr(handlers.aioboto3, "Session", lambda: session)
    monkeypatch.setattr(
        handlers,
        "WorkflowSettings",
        lambda: settings,
    )
    monkeypatch.setattr(
        handlers,
        "build_upload_session_repository",
        lambda **kwargs: {"upload_session": kwargs},
    )
    monkeypatch.setattr(
        handlers,
        "build_transfer_usage_window_repository",
        lambda **kwargs: {"usage": kwargs},
    )
    monkeypatch.setattr(
        handlers,
        "TransferReconciliationService",
        _FakeReconciliationService,
    )

    result = await handlers._reconcile_transfer_state(event={})

    assert result == {"status": "ok"}
    assert [name for name, _ in session.client_calls] == ["s3"]
    assert [name for name, _ in session.resource_calls] == ["dynamodb"]
    assert isinstance(session.client_calls[0][1], Config)
    assert session.client_calls[0][1].s3 == {"use_accelerate_endpoint": True}
    assert isinstance(session.resource_calls[0][1], Config)
