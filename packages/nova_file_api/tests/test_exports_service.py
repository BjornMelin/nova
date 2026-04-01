"""Unit tests for export service status-update adapter semantics."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nova_file_api.errors import FileTransferError
from nova_file_api.exports import ExportService, MemoryExportPublisher
from nova_file_api.metrics import MetricsCollector
from nova_runtime_support.export_models import ExportRecord, ExportStatus
from nova_runtime_support.export_runtime import MemoryExportRepository


async def _build_service_with_record(
    *,
    status: ExportStatus = ExportStatus.QUEUED,
) -> ExportService:
    repository = MemoryExportRepository()
    now = datetime.now(tz=UTC)
    await repository.create(
        ExportRecord(
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
    )
    return ExportService(
        repository=repository,
        publisher=MemoryExportPublisher(process_immediately=False),
        metrics=MetricsCollector(namespace="Tests"),
    )


@pytest.mark.anyio
async def test_update_status_maps_missing_export_to_not_found() -> None:
    service = ExportService(
        repository=MemoryExportRepository(),
        publisher=MemoryExportPublisher(process_immediately=False),
        metrics=MetricsCollector(namespace="Tests"),
    )

    with pytest.raises(FileTransferError) as exc_info:
        await service.update_status(
            export_id="missing",
            status=ExportStatus.VALIDATING,
        )

    assert exc_info.value.code == "not_found"
    assert exc_info.value.message == "export not found"


@pytest.mark.anyio
async def test_update_status_maps_invalid_transition_to_conflict() -> None:
    service = await _build_service_with_record(status=ExportStatus.SUCCEEDED)

    with pytest.raises(FileTransferError) as exc_info:
        await service.update_status(
            export_id="export-1",
            status=ExportStatus.VALIDATING,
        )

    assert exc_info.value.code == "conflict"
    assert exc_info.value.message == "invalid export state transition"
    assert exc_info.value.details == {
        "export_id": "export-1",
        "current_status": "succeeded",
        "requested_status": "validating",
    }
