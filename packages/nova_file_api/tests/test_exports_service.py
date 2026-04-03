"""Unit tests for export service status-update adapter semantics."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nova_file_api.errors import FileTransferError
from nova_file_api.exports import ExportService, MemoryExportPublisher
from nova_file_api.metrics import MetricsCollector
from nova_runtime_support.export_models import ExportRecord, ExportStatus
from nova_runtime_support.export_runtime import MemoryExportRepository


class _RecordingExportPublisher(MemoryExportPublisher):
    def __init__(self) -> None:
        super().__init__(process_immediately=False)
        self.stop_calls: list[dict[str, str]] = []

    async def publish(self, *, export: ExportRecord) -> str | None:
        del export
        return "arn:aws:states:::execution:test"

    async def stop_execution(self, *, execution_arn: str, cause: str) -> None:
        self.stop_calls.append({"execution_arn": execution_arn, "cause": cause})


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
async def test_create_and_cancel_export_tracks_execution_metadata() -> None:
    repository = MemoryExportRepository()
    publisher = _RecordingExportPublisher()
    service = ExportService(
        repository=repository,
        publisher=publisher,
        metrics=MetricsCollector(namespace="Tests"),
    )

    created = await service.create(
        source_key="uploads/scope-1/source.csv",
        filename="source.csv",
        scope_id="scope-1",
    )
    assert created.execution_arn == "arn:aws:states:::execution:test"
    assert created.cancel_requested_at is None

    cancelled = await service.cancel(
        export_id=created.export_id,
        scope_id="scope-1",
    )
    assert cancelled.status == ExportStatus.CANCELLED
    assert cancelled.cancel_requested_at is not None
    assert publisher.stop_calls == [
        {
            "execution_arn": "arn:aws:states:::execution:test",
            "cause": "export cancelled by caller",
        }
    ]


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
