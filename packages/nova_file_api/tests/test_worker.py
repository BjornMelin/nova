from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.config import Settings
from nova_file_api.errors import upstream_s3_error
from nova_file_api.exports import (
    ExportService,
    MemoryExportPublisher,
    MemoryExportRepository,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import ExportRecord, ExportStatus
from nova_file_api.transfer import ExportCopyResult, TransferService
from nova_file_api.worker import JobsWorker


class _FakeSqsClient:
    def __init__(self) -> None:
        self.delete_calls: list[dict[str, Any]] = []
        self.change_visibility_calls: list[dict[str, Any]] = []

    async def delete_message(self, **kwargs: Any) -> None:
        self.delete_calls.append(kwargs)

    async def change_message_visibility(self, **kwargs: Any) -> None:
        self.change_visibility_calls.append(kwargs)


class _FakeTransferService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result: ExportCopyResult | None = None
        self.error: Exception | None = None

    async def copy_upload_to_export(
        self,
        *,
        source_bucket: str,
        source_key: str,
        scope_id: str,
        export_id: str,
        filename: str,
    ) -> ExportCopyResult:
        self.calls.append(
            {
                "source_bucket": source_bucket,
                "source_key": source_key,
                "scope_id": scope_id,
                "export_id": export_id,
                "filename": filename,
            }
        )
        if self.error is not None:
            raise self.error
        return self.result or ExportCopyResult(
            export_key=f"exports/{scope_id}/{export_id}/{filename}",
            download_filename=filename,
        )


def _worker_settings() -> Settings:
    return Settings.model_validate(
        {
            "JOBS_ENABLED": True,
            "JOBS_RUNTIME_MODE": "worker",
            "JOBS_QUEUE_BACKEND": "sqs",
            "JOBS_SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/export-queue",
            "JOBS_REPOSITORY_BACKEND": "dynamodb",
            "JOBS_DYNAMODB_TABLE": "exports-table",
            "ACTIVITY_STORE_BACKEND": "dynamodb",
            "ACTIVITY_ROLLUPS_TABLE": "activity-table",
            "FILE_TRANSFER_BUCKET": "test-transfer-bucket",
        }
    )


async def _build_worker_runtime(
    *,
    export_id: str = "export-1",
    status: ExportStatus = ExportStatus.QUEUED,
) -> tuple[MemoryExportRepository, ExportService, MemoryActivityStore]:
    repository = MemoryExportRepository()
    metrics = MetricsCollector(namespace="Tests")
    service = ExportService(
        repository=repository,
        publisher=MemoryExportPublisher(process_immediately=False),
        metrics=metrics,
    )
    now = datetime.now(tz=UTC)
    await repository.create(
        ExportRecord(
            export_id=export_id,
            scope_id="scope-1",
            request_id=None,
            source_key="uploads/scope-1/source.csv",
            filename="source.csv",
            status=status,
            output=None,
            error=None,
            created_at=now,
            updated_at=now,
        )
    )
    return repository, service, MemoryActivityStore()


def _worker_message_body(
    *,
    export_id: str = "export-1",
    scope_id: str = "scope-1",
    source_key: str = "uploads/scope-1/source.csv",
    filename: str = "source.csv",
) -> str:
    return json.dumps(
        {
            "export_id": export_id,
            "scope_id": scope_id,
            "source_key": source_key,
            "filename": filename,
            "created_at": datetime.now(tz=UTC).isoformat(),
        }
    )


def _build_worker(*, transfer_service: _FakeTransferService) -> JobsWorker:
    return JobsWorker(
        settings=_worker_settings(),
        transfer_service=cast(TransferService, transfer_service),
    )


async def _attach_runtime(
    *,
    worker: JobsWorker,
    transfer_service: _FakeTransferService,
    export_service: ExportService,
    activity_store: MemoryActivityStore,
) -> _FakeSqsClient:
    sqs_client = _FakeSqsClient()
    worker._sqs = sqs_client
    worker._runtime_transfer_service = transfer_service  # type: ignore[assignment]
    worker._runtime_export_service = export_service
    worker._runtime_activity_store = activity_store
    return sqs_client


@pytest.mark.asyncio
async def test_worker_invalid_message_is_not_deleted() -> None:
    transfer_service = _FakeTransferService()
    repository, export_service, activity_store = await _build_worker_runtime()
    worker = _build_worker(transfer_service=transfer_service)
    await _attach_runtime(
        worker=worker,
        transfer_service=transfer_service,
        export_service=export_service,
        activity_store=activity_store,
    )

    should_delete = await worker._handle_message(
        message={"MessageId": "msg-1", "Body": "{}"}
    )

    assert should_delete is False
    assert await repository.get("export-1") is not None


@pytest.mark.asyncio
async def test_worker_executes_export_and_marks_success() -> None:
    transfer_service = _FakeTransferService()
    repository, export_service, activity_store = await _build_worker_runtime(
        export_id="export-2"
    )
    worker = _build_worker(transfer_service=transfer_service)
    await _attach_runtime(
        worker=worker,
        transfer_service=transfer_service,
        export_service=export_service,
        activity_store=activity_store,
    )

    should_delete = await worker._handle_message(
        message={
            "MessageId": "msg-2",
            "ReceiptHandle": "rh-2",
            "Body": _worker_message_body(export_id="export-2"),
        }
    )

    record = await repository.get("export-2")
    assert should_delete is True
    assert record is not None
    assert record.status == ExportStatus.SUCCEEDED
    assert record.output is not None
    assert record.output.key.endswith("/export-2/source.csv")
    assert transfer_service.calls[0]["export_id"] == "export-2"


@pytest.mark.asyncio
async def test_worker_retryable_error_leaves_message_unacked() -> None:
    transfer_service = _FakeTransferService()
    transfer_service.error = upstream_s3_error(
        "failed to copy upload object to export key"
    )
    repository, export_service, activity_store = await _build_worker_runtime(
        export_id="export-3"
    )
    worker = _build_worker(transfer_service=transfer_service)
    await _attach_runtime(
        worker=worker,
        transfer_service=transfer_service,
        export_service=export_service,
        activity_store=activity_store,
    )

    should_delete = await worker._handle_message(
        message={
            "MessageId": "msg-3",
            "ReceiptHandle": "rh-3",
            "Body": _worker_message_body(export_id="export-3"),
        }
    )

    record = await repository.get("export-3")
    assert should_delete is False
    assert record is not None
    assert record.status == ExportStatus.COPYING


@pytest.mark.asyncio
async def test_worker_acks_terminal_redelivery_without_reprocessing() -> None:
    transfer_service = _FakeTransferService()
    repository, export_service, activity_store = await _build_worker_runtime(
        export_id="export-4",
        status=ExportStatus.SUCCEEDED,
    )
    worker = _build_worker(transfer_service=transfer_service)
    await _attach_runtime(
        worker=worker,
        transfer_service=transfer_service,
        export_service=export_service,
        activity_store=activity_store,
    )

    should_delete = await worker._handle_message(
        message={
            "MessageId": "msg-4",
            "ReceiptHandle": "rh-4",
            "Body": _worker_message_body(export_id="export-4"),
        }
    )

    assert should_delete is True
    assert transfer_service.calls == []
    assert (await repository.get("export-4")) is not None
