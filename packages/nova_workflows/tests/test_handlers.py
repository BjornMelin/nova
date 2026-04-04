from __future__ import annotations

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from nova_runtime_support.export_copy_worker import ExportCopyTaskMessage
from nova_workflows import handlers


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
