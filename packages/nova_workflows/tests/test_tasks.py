from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from nova_file_api.export_models import ExportRecord, ExportStatus
from nova_file_api.workflow_facade import (
    ExportCopyPollResult,
    ExportCopyResult,
    ExportCopyStrategy,
    ExportTransferService,
    MemoryExportRepository,
    NoopExportMetrics,
    PreparedExportCopy,
    QueuedExportCopyState,
    WorkflowExportStateService,
)
from nova_workflows.models import ExportWorkflowInput, WorkflowOutput
from nova_workflows.tasks import (
    copy_export,
    fail_export,
    finalize_export,
    poll_queued_export_copy,
    prepare_export_copy,
    start_queued_export_copy,
    validate_export,
)


class _FakeTransferService:
    def __init__(self) -> None:
        self.deleted_export_keys: list[str] = []

    async def copy_upload_to_export(
        self,
        *,
        source_bucket: str,
        source_key: str,
        scope_id: str,
        export_id: str,
        filename: str,
    ) -> ExportCopyResult:
        assert source_bucket == "test-bucket"
        assert source_key == "uploads/scope-1/source.csv"
        assert scope_id == "scope-1"
        assert export_id == "export-1"
        assert filename == "source.csv"
        return ExportCopyResult(
            export_key="exports/scope-1/export-1/source.csv",
            download_filename="source.csv",
        )

    async def delete_export_object(self, *, export_key: str) -> None:
        self.deleted_export_keys.append(export_key)


class _FakeLargeCopyService:
    async def prepare(self, *, export: ExportRecord) -> PreparedExportCopy:
        assert export.export_id == "export-1"
        return PreparedExportCopy(
            export_key="exports/scope-1/export-1/source.csv",
            download_filename="source.csv",
            source_size_bytes=60 * 1024 * 1024 * 1024,
            copy_part_size_bytes=2 * 1024 * 1024 * 1024,
            copy_part_count=30,
            strategy=ExportCopyStrategy.WORKER,
        )

    async def start(
        self,
        *,
        export: ExportRecord,
        prepared: PreparedExportCopy,
    ) -> QueuedExportCopyState:
        assert export.export_id == "export-1"
        assert prepared.strategy == ExportCopyStrategy.WORKER
        return QueuedExportCopyState(
            export_key=prepared.export_key,
            upload_id="worker-upload-id",
            copy_part_count=prepared.copy_part_count,
            copy_part_size_bytes=prepared.copy_part_size_bytes,
        )

    async def poll(
        self,
        *,
        export: ExportRecord,
        upload_id: str,
        export_key: str,
        download_filename: str,
    ) -> ExportCopyPollResult:
        assert export.export_id == "export-1"
        assert upload_id == "worker-upload-id"
        assert export_key == "exports/scope-1/export-1/source.csv"
        assert download_filename == "source.csv"
        return ExportCopyPollResult(
            state="ready",
            completed_parts=30,
            total_parts=30,
            output_key=export_key,
            download_filename=download_filename,
        )


async def _service_with_record(
    *,
    status: ExportStatus = ExportStatus.QUEUED,
) -> tuple[
    MemoryExportRepository,
    WorkflowExportStateService,
]:
    repository = MemoryExportRepository()
    service = WorkflowExportStateService(
        repository=repository,
        metrics=NoopExportMetrics(),
    )
    now = datetime.now(tz=UTC)
    record = ExportRecord(
        export_id="export-1",
        scope_id="scope-1",
        request_id="req-1",
        source_key="uploads/scope-1/source.csv",
        filename="source.csv",
        status=status,
        output=None,
        error=None,
        created_at=now,
        updated_at=now,
    )
    await repository.create(record)
    return repository, service


def _workflow_input() -> ExportWorkflowInput:
    now = datetime.now(tz=UTC)
    return ExportWorkflowInput(
        export_id="export-1",
        scope_id="scope-1",
        source_key="uploads/scope-1/source.csv",
        filename="source.csv",
        request_id="req-1",
        status=ExportStatus.QUEUED,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )


@pytest.mark.anyio
async def test_validate_copy_finalize_workflow_tasks() -> None:
    repository, export_service = await _service_with_record()
    transfer_service = _FakeTransferService()
    workflow_input = await validate_export(
        workflow_input=_workflow_input(),
        export_service=export_service,
    )
    validating = await repository.get("export-1")
    assert validating is not None
    assert validating.status == ExportStatus.VALIDATING

    copied = await copy_export(
        workflow_input=workflow_input,
        export_service=export_service,
        transfer_service=cast(ExportTransferService, transfer_service),
        file_transfer_bucket="test-bucket",
    )
    assert copied.output == WorkflowOutput(
        key="exports/scope-1/export-1/source.csv",
        download_filename="source.csv",
    )
    copying = await repository.get("export-1")
    assert copying is not None
    assert copying.status == ExportStatus.COPYING

    finalized = await finalize_export(
        workflow_input=copied,
        export_service=export_service,
    )
    finished = await repository.get("export-1")
    assert finished is not None
    assert finished.status == ExportStatus.SUCCEEDED
    assert finished.output is not None
    assert finalized.status == ExportStatus.SUCCEEDED


@pytest.mark.anyio
async def test_fail_export_persists_error_detail() -> None:
    repository, export_service = await _service_with_record()
    failed_input = _workflow_input().model_copy(
        update={"error": "TaskFailed", "cause": "copy task timed out"}
    )

    failed = await fail_export(
        workflow_input=failed_input,
        export_service=export_service,
    )

    finished = await repository.get("export-1")
    assert finished is not None
    assert finished.status == ExportStatus.FAILED
    assert finished.error == "copy task timed out"
    assert failed.status == ExportStatus.FAILED


@pytest.mark.anyio
async def test_copy_export_cleans_up_when_export_is_cancelled_mid_copy() -> (
    None
):
    repository, export_service = await _service_with_record()

    class _CancellingTransferService(_FakeTransferService):
        async def copy_upload_to_export(
            self,
            *,
            source_bucket: str,
            source_key: str,
            scope_id: str,
            export_id: str,
            filename: str,
        ) -> ExportCopyResult:
            result = await super().copy_upload_to_export(
                source_bucket=source_bucket,
                source_key=source_key,
                scope_id=scope_id,
                export_id=export_id,
                filename=filename,
            )
            current = await repository.get(export_id)
            assert current is not None
            await repository.update(
                current.model_copy(update={"status": ExportStatus.CANCELLED})
            )
            return result

    transfer_service = _CancellingTransferService()
    workflow_input = await validate_export(
        workflow_input=_workflow_input(),
        export_service=export_service,
    )

    copied = await copy_export(
        workflow_input=workflow_input,
        export_service=export_service,
        transfer_service=cast(ExportTransferService, transfer_service),
        file_transfer_bucket="test-bucket",
    )

    stored = await repository.get("export-1")
    assert copied.copy_progress_state == "cancelled"
    assert copied.output is None
    assert stored is not None
    assert stored.status == ExportStatus.CANCELLED
    assert transfer_service.deleted_export_keys == [
        "exports/scope-1/export-1/source.csv"
    ]


@pytest.mark.anyio
async def test_finalize_export_noops_when_cancelled() -> None:
    repository, export_service = await _service_with_record(
        status=ExportStatus.CANCELLED
    )

    result = await finalize_export(
        workflow_input=_workflow_input().model_copy(
            update={
                "output": WorkflowOutput(
                    key="exports/scope-1/export-1/source.csv",
                    download_filename="source.csv",
                )
            }
        ),
        export_service=export_service,
    )

    stored = await repository.get("export-1")
    assert result.status == ExportStatus.CANCELLED
    assert stored is not None
    assert stored.status == ExportStatus.CANCELLED


@pytest.mark.anyio
async def test_fail_export_noops_when_cancelled() -> None:
    repository, export_service = await _service_with_record(
        status=ExportStatus.CANCELLED
    )

    result = await fail_export(
        workflow_input=_workflow_input().model_copy(
            update={"error": "TaskFailed", "cause": "late failure"}
        ),
        export_service=export_service,
    )

    stored = await repository.get("export-1")
    assert result.status == ExportStatus.CANCELLED
    assert stored is not None
    assert stored.status == ExportStatus.CANCELLED


@pytest.mark.anyio
async def test_prepare_and_queue_worker_export_copy_tasks() -> None:
    _repository, export_service = await _service_with_record()
    workflow_input = await validate_export(
        workflow_input=_workflow_input(),
        export_service=export_service,
    )

    prepared = await prepare_export_copy(
        workflow_input=workflow_input,
        export_service=export_service,
        large_copy_service=_FakeLargeCopyService(),
    )

    assert prepared.copy_strategy == "worker"
    assert prepared.output == WorkflowOutput(
        key="exports/scope-1/export-1/source.csv",
        download_filename="source.csv",
    )

    queued = await start_queued_export_copy(
        workflow_input=prepared,
        export_service=export_service,
        large_copy_service=_FakeLargeCopyService(),
    )

    assert queued.copy_upload_id == "worker-upload-id"
    assert queued.copy_progress_state == "pending"
    assert queued.copy_total_parts == 30

    polled = await poll_queued_export_copy(
        workflow_input=queued,
        export_service=export_service,
        large_copy_service=_FakeLargeCopyService(),
    )

    assert polled.copy_progress_state == "ready"
    assert polled.copy_completed_parts == 30
