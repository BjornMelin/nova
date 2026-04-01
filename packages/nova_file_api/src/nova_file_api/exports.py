"""Export workflow services and shared repository/publisher bindings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from nova_file_api.errors import conflict, not_found, queue_unavailable
from nova_file_api.metrics import MetricsCollector
from nova_runtime_support.export_models import (
    ExportOutput,
    ExportRecord,
    ExportStatus,
)
from nova_runtime_support.export_runtime import (
    DynamoExportRepository,
    DynamoResource,
    ExportPublisher,
    ExportPublishError,
    ExportRepository,
    MemoryExportPublisher,
    MemoryExportRepository,
    StepFunctionsClient,
    StepFunctionsExportPublisher,
    export_status_transition_allowed,
    queue_lag_ms,
    utc_now,
)


@dataclass(slots=True)
class ExportService:
    """Export orchestration service for create/status/cancel endpoints."""

    repository: ExportRepository
    publisher: ExportPublisher
    metrics: MetricsCollector

    async def create(
        self,
        *,
        source_key: str,
        filename: str,
        scope_id: str,
        request_id: str | None = None,
    ) -> ExportRecord:
        """Create and enqueue an export workflow record."""
        now = _utc_now()
        record = ExportRecord(
            export_id=uuid4().hex,
            scope_id=scope_id,
            request_id=request_id,
            source_key=source_key,
            filename=filename,
            status=ExportStatus.QUEUED,
            output=None,
            error=None,
            created_at=now,
            updated_at=now,
        )
        await self.repository.create(record)
        try:
            await self.publisher.publish(export=record)
        except ExportPublishError as exc:
            failed = record.model_copy(
                update={
                    "status": ExportStatus.FAILED,
                    "error": "queue_unavailable",
                    "updated_at": _utc_now(),
                }
            )
            await self.repository.update(failed)
            self.metrics.incr("exports_publish_failed")
            raise queue_unavailable(
                "export creation failed because queue publish failed",
                details=exc.details,
            ) from exc

        self.metrics.incr("exports_created")
        await self.publisher.post_publish(
            export=record,
            repository=self.repository,
            metrics=self.metrics,
        )

        return (await self.repository.get(record.export_id)) or record

    async def get(self, *, export_id: str, scope_id: str) -> ExportRecord:
        """Return export by id when owned by caller scope."""
        record = await self.repository.get(export_id)
        if record is None or record.scope_id != scope_id:
            raise not_found("export not found")
        return record

    async def list_for_scope(
        self, *, scope_id: str, limit: int = 50
    ) -> list[ExportRecord]:
        """List exports for caller scope, newest first."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        return await self.repository.list_for_scope(
            scope_id=scope_id,
            limit=limit,
        )

    async def cancel(self, *, export_id: str, scope_id: str) -> ExportRecord:
        """Cancel a non-terminal export when owned by the caller."""
        for _ in range(MAX_CANCEL_RETRIES):
            record = await self.get(export_id=export_id, scope_id=scope_id)
            if record.status in {
                ExportStatus.SUCCEEDED,
                ExportStatus.FAILED,
                ExportStatus.CANCELLED,
            }:
                return record
            updated = record.model_copy(
                update={
                    "status": ExportStatus.CANCELLED,
                    "updated_at": _utc_now(),
                }
            )
            updated_ok = await self.repository.update_if_status(
                record=updated,
                expected_status=record.status,
            )
            if updated_ok:
                self.metrics.incr("exports_cancelled")
                return updated
        raise conflict(
            "cancel failed after max retries",
            details={
                "export_id": export_id,
                "scope_id": scope_id,
                "max_retries": MAX_CANCEL_RETRIES,
            },
        )

    async def update_status(
        self,
        *,
        export_id: str,
        status: ExportStatus,
        output: ExportOutput | None = None,
        error: str | None = None,
    ) -> ExportRecord:
        """Update export output/status from workflow-side processing."""
        record = await self.repository.get(export_id)
        if record is None:
            raise not_found("export not found")
        if not export_status_transition_allowed(
            current=record.status,
            target=status,
        ):
            raise conflict(
                "invalid export state transition",
                details={
                    "export_id": export_id,
                    "current_status": record.status.value,
                    "requested_status": status.value,
                },
            )

        now = _utc_now()
        update_payload: dict[str, object] = {
            "status": status,
            "updated_at": now,
        }
        queued_lag_ms: float | None = None
        if (
            record.status == ExportStatus.QUEUED
            and status != ExportStatus.QUEUED
        ):
            queued_lag_ms = queue_lag_ms(created_at=record.created_at, now=now)
        if output is not None:
            update_payload["output"] = output
        if error is not None:
            update_payload["error"] = error
        if status == ExportStatus.SUCCEEDED:
            if output is None and record.output is None:
                raise conflict("export output is required for succeeded status")
            update_payload["output"] = output or record.output
            update_payload["error"] = None
        if status == ExportStatus.FAILED and error is None:
            update_payload["error"] = record.error or "export_failed"

        updated = record.model_copy(update=update_payload)
        updated_ok = await self.repository.update_if_status(
            record=updated,
            expected_status=record.status,
        )
        if not updated_ok:
            latest = await self.repository.get(export_id)
            if latest is None:
                raise not_found("export not found")
            if latest.status == status:
                return latest
            raise conflict(
                "invalid export state transition",
                details={
                    "export_id": export_id,
                    "current_status": latest.status.value,
                    "requested_status": status.value,
                },
            )

        if queued_lag_ms is not None:
            self.metrics.observe_ms("exports_queue_lag_ms", queued_lag_ms)
            self.metrics.emit_emf(
                metric_name="exports_queue_lag_ms",
                value=queued_lag_ms,
                unit="Milliseconds",
                dimensions={"source": "export_status_update"},
            )
        self.metrics.incr(f"exports_{status.value}")
        self.metrics.incr("exports_status_updates_total")
        self.metrics.incr(f"exports_status_updates_{status.value}")
        self.metrics.emit_emf(
            metric_name="exports_status_updates_total",
            value=1,
            unit="Count",
            dimensions={"status": status.value},
        )
        return updated


def _utc_now() -> datetime:
    now = utc_now()
    return now if now.tzinfo is not None else now.replace(tzinfo=UTC)


MAX_CANCEL_RETRIES = 8


__all__ = [
    "MAX_CANCEL_RETRIES",
    "DynamoExportRepository",
    "DynamoResource",
    "ExportOutput",
    "ExportPublishError",
    "ExportPublisher",
    "ExportRecord",
    "ExportRepository",
    "ExportService",
    "ExportStatus",
    "MemoryExportPublisher",
    "MemoryExportRepository",
    "StepFunctionsClient",
    "StepFunctionsExportPublisher",
]
