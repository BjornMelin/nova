from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from nova_runtime_support.export_models import ExportRecord, ExportStatus
from nova_runtime_support.export_runtime import (
    MemoryExportPublisher,
    MemoryExportRepository,
    NoopExportMetrics,
    WorkflowExportStateService,
)
from nova_runtime_support.export_transfer import (
    ExportCopyResult,
    ExportTransferService,
)
from nova_workflows.models import ExportWorkflowInput, WorkflowOutput
from nova_workflows.tasks import (
    copy_export,
    fail_export,
    finalize_export,
    validate_export,
)


class _FakeTransferService:
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


async def _service_with_record() -> tuple[
    MemoryExportRepository,
    WorkflowExportStateService,
]:
    repository = MemoryExportRepository()
    service = WorkflowExportStateService(
        repository=repository,
        metrics=NoopExportMetrics(),
    )
    publisher = MemoryExportPublisher(process_immediately=False)
    now = datetime.now(tz=UTC)
    record = ExportRecord(
        export_id="export-1",
        scope_id="scope-1",
        request_id="req-1",
        source_key="uploads/scope-1/source.csv",
        filename="source.csv",
        status=ExportStatus.QUEUED,
        output=None,
        error=None,
        created_at=now,
        updated_at=now,
    )
    await repository.create(record)
    await publisher.publish(export=record)
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
        transfer_service=cast(ExportTransferService, _FakeTransferService()),
        file_transfer_bucket="test-bucket",
    )
    assert copied.output == WorkflowOutput(
        key="exports/scope-1/export-1/source.csv",
        download_filename="source.csv",
    )
    copying = await repository.get("export-1")
    assert copying is not None
    assert copying.status == ExportStatus.COPYING

    await finalize_export(
        workflow_input=copied,
        export_service=export_service,
    )
    finished = await repository.get("export-1")
    assert finished is not None
    assert finished.status == ExportStatus.SUCCEEDED
    assert finished.output is not None


@pytest.mark.anyio
async def test_fail_export_persists_error_detail() -> None:
    repository, export_service = await _service_with_record()
    failed_input = _workflow_input().model_copy(
        update={"error": "TaskFailed", "cause": "copy task timed out"}
    )

    await fail_export(
        workflow_input=failed_input,
        export_service=export_service,
    )

    finished = await repository.get("export-1")
    assert finished is not None
    assert finished.status == ExportStatus.FAILED
    assert finished.error == "copy task timed out"
