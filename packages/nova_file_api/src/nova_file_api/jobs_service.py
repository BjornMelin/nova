"""Async job orchestration service and state transitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from nova_file_api.errors import conflict, not_found, queue_unavailable
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import JobRecord, JobStatus

from .jobs_publisher import JobPublisher, JobPublishError
from .jobs_repository import JobRepository

_ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.PENDING: {
        JobStatus.PENDING,
        JobStatus.RUNNING,
        JobStatus.SUCCEEDED,
        JobStatus.FAILED,
        JobStatus.CANCELED,
    },
    JobStatus.RUNNING: {
        JobStatus.RUNNING,
        JobStatus.SUCCEEDED,
        JobStatus.FAILED,
        JobStatus.CANCELED,
    },
    JobStatus.SUCCEEDED: {JobStatus.SUCCEEDED},
    JobStatus.FAILED: {JobStatus.FAILED},
    JobStatus.CANCELED: {JobStatus.CANCELED},
}
MAX_CANCEL_RETRIES = 8


@dataclass(slots=True)
class JobService:
    """Job orchestration service for enqueue/status/cancel endpoints."""

    repository: JobRepository
    publisher: JobPublisher
    metrics: MetricsCollector

    def enqueue(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        scope_id: str,
    ) -> JobRecord:
        """Create a new job record and enqueue it for execution."""
        now = _utc_now()
        record = JobRecord(
            job_id=uuid4().hex,
            job_type=job_type,
            scope_id=scope_id,
            status=JobStatus.PENDING,
            payload=payload,
            result=None,
            error=None,
            created_at=now,
            updated_at=now,
        )
        self.repository.create(record)
        try:
            self.publisher.publish(job=record)
        except JobPublishError as exc:
            failed = record.model_copy(
                update={
                    "status": JobStatus.FAILED,
                    "error": "queue_unavailable",
                    "updated_at": _utc_now(),
                }
            )
            self.repository.update(failed)
            self.metrics.incr("jobs_publish_failed")
            raise queue_unavailable(
                "job enqueue failed because queue publish failed",
                details=exc.details,
            ) from exc

        self.metrics.incr("jobs_enqueued")
        self.publisher.post_publish(
            job=record,
            repository=self.repository,
            metrics=self.metrics,
        )
        return self.repository.get(record.job_id) or record

    def get(self, *, job_id: str, scope_id: str) -> JobRecord:
        """Return one caller-owned job record."""
        record = self.repository.get(job_id)
        if record is None or record.scope_id != scope_id:
            raise not_found("job not found")
        return record

    def cancel(self, *, job_id: str, scope_id: str) -> JobRecord:
        """Cancel one caller-owned non-terminal job."""
        for _ in range(MAX_CANCEL_RETRIES):
            record = self.get(job_id=job_id, scope_id=scope_id)
            if record.status in {
                JobStatus.SUCCEEDED,
                JobStatus.FAILED,
                JobStatus.CANCELED,
            }:
                return record
            updated = record.model_copy(
                update={
                    "status": JobStatus.CANCELED,
                    "updated_at": _utc_now(),
                }
            )
            if self.repository.update_if_status(
                record=updated,
                expected_status=record.status,
            ):
                self.metrics.incr("jobs_canceled")
                return updated
        raise conflict(
            "cancel failed after max retries",
            details={
                "job_id": job_id,
                "scope_id": scope_id,
                "max_retries": MAX_CANCEL_RETRIES,
            },
        )

    def list_for_scope(
        self,
        *,
        scope_id: str,
        limit: int = 50,
    ) -> list[JobRecord]:
        """List caller-owned jobs newest first."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        return self.repository.list_for_scope(scope_id=scope_id, limit=limit)

    def retry(self, *, job_id: str, scope_id: str) -> JobRecord:
        """Retry one failed or canceled caller-owned job."""
        original = self.get(job_id=job_id, scope_id=scope_id)
        if original.status not in {JobStatus.FAILED, JobStatus.CANCELED}:
            raise conflict(
                "job retry is only allowed from failed or canceled states",
                details={
                    "job_id": job_id,
                    "current_status": original.status.value,
                },
            )
        return self.enqueue(
            job_type=original.job_type,
            payload=original.payload,
            scope_id=scope_id,
        )

    def update_result(
        self,
        *,
        job_id: str,
        status: JobStatus,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> JobRecord:
        """Apply one worker result update using validated state transitions."""
        record = self.repository.get(job_id)
        if record is None:
            raise not_found("job not found")
        if not is_valid_transition(current=record.status, target=status):
            raise conflict(
                "invalid job state transition",
                details={
                    "job_id": job_id,
                    "current_status": record.status.value,
                    "requested_status": status.value,
                },
            )

        now = _utc_now()
        update_payload: dict[str, Any] = {
            "status": status,
            "updated_at": now,
        }
        queue_lag_ms: float | None = None
        if record.status == JobStatus.PENDING and status != JobStatus.PENDING:
            queue_lag_ms = queue_lag_ms_since(
                created_at=record.created_at,
                now=now,
            )
        if result is not None:
            update_payload["result"] = result
        if error is not None:
            update_payload["error"] = error
        if status == JobStatus.SUCCEEDED:
            if result is None:
                update_payload["result"] = record.result or {}
            update_payload["error"] = None
        if status == JobStatus.FAILED and error is None:
            update_payload["error"] = record.error or "worker_failed"

        updated = record.model_copy(update=update_payload)
        if not self.repository.update_if_status(
            record=updated,
            expected_status=record.status,
        ):
            latest = self.repository.get(job_id)
            if latest is None:
                raise not_found("job not found")
            if latest.status == status:
                return latest
            raise conflict(
                "invalid job state transition",
                details={
                    "job_id": job_id,
                    "current_status": latest.status.value,
                    "requested_status": status.value,
                },
            )

        if queue_lag_ms is not None:
            self.metrics.observe_ms("jobs_queue_lag_ms", queue_lag_ms)
            self.metrics.emit_emf(
                metric_name="jobs_queue_lag_ms",
                value=queue_lag_ms,
                unit="Milliseconds",
                dimensions={"source": "worker_result_update"},
            )
        self.metrics.incr(f"jobs_{status.value}")
        self.metrics.incr("jobs_worker_result_updates_total")
        self.metrics.incr(f"jobs_worker_result_updates_{status.value}")
        self.metrics.emit_emf(
            metric_name="jobs_worker_result_updates_total",
            value=1,
            unit="Count",
            dimensions={"status": status.value},
        )
        return updated


def is_valid_transition(*, current: JobStatus, target: JobStatus) -> bool:
    """Return whether a status transition is allowed."""
    return target in _ALLOWED_TRANSITIONS[current]


def queue_lag_ms_since(*, created_at: datetime, now: datetime) -> float:
    """Calculate queue lag in milliseconds using UTC-safe timestamps."""
    created = (
        created_at
        if created_at.tzinfo is not None
        else created_at.replace(tzinfo=UTC)
    )
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    lag_ms = (current - created).total_seconds() * 1000.0
    return max(0.0, lag_ms)


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)
