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
    ExportStatusLookupError,
    ExportStatusOutputRequiredError,
    ExportStatusTransitionError,
    MemoryExportPublisher,
    MemoryExportRepository,
    StepFunctionsClient,
    StepFunctionsExportPublisher,
    update_export_status_shared,
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
            execution_arn=None,
            cancel_requested_at=None,
            created_at=now,
            updated_at=now,
        )
        await self.repository.create(record)
        try:
            execution_arn = await self.publisher.publish(export=record)
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

        if execution_arn is not None:
            record = record.model_copy(
                update={
                    "execution_arn": execution_arn,
                    "updated_at": _utc_now(),
                }
            )
            await self.repository.update(record)

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
            cancel_requested_at = _utc_now()
            updated = record.model_copy(
                update={
                    "status": ExportStatus.CANCELLED,
                    "cancel_requested_at": cancel_requested_at,
                    "updated_at": _utc_now(),
                }
            )
            updated_ok = await self.repository.update_if_status(
                record=updated,
                expected_status=record.status,
            )
            if updated_ok:
                if record.execution_arn is not None:
                    await self.publisher.stop_execution(
                        execution_arn=record.execution_arn,
                        cause="export cancelled by caller",
                    )
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
        try:
            return await update_export_status_shared(
                repository=self.repository,
                metrics=self.metrics,
                export_id=export_id,
                status=status,
                output=output,
                error=error,
            )
        except ExportStatusLookupError as exc:
            raise not_found("export not found") from exc
        except ExportStatusOutputRequiredError as exc:
            raise conflict(
                str(exc),
            ) from exc
        except ExportStatusTransitionError as exc:
            details = {
                "export_id": exc.export_id,
                "requested_status": exc.requested_status.value,
            }
            if exc.current_status is not None:
                details["current_status"] = exc.current_status.value
            raise conflict(
                str(exc),
                details=details,
            ) from exc


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
