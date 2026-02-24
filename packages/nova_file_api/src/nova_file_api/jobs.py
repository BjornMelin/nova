"""Async job APIs and queue abstractions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Protocol
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.errors import conflict, not_found, queue_unavailable
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import JobRecord, JobStatus


class JobRepository(Protocol):
    """Persist and retrieve job records."""

    def create(self, record: JobRecord) -> None:
        """Persist a new job record."""

    def get(self, job_id: str) -> JobRecord | None:
        """Return job record by id if present."""

    def update(self, record: JobRecord) -> None:
        """Replace a job record."""

    def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        """Replace record only when current status matches expected value."""


class JobPublisher(Protocol):
    """Queue interface for background job dispatch."""

    def publish(self, *, job: JobRecord) -> None:
        """Publish job record to background queue."""

    def post_publish(
        self,
        *,
        job: JobRecord,
        repository: JobRepository,
        metrics: MetricsCollector,
    ) -> None:
        """Run optional post-publish handling."""


@dataclass(slots=True)
class JobPublishError(Exception):
    """Raised when queue publish fails and enqueue cannot proceed."""

    details: dict[str, Any]

    def __post_init__(self) -> None:
        """Provide a stable Exception message for logging surfaces."""
        Exception.__init__(self, "queue publish failed")


@dataclass(slots=True)
class MemoryJobRepository:
    """In-memory job record repository."""

    _records: dict[str, JobRecord]
    _lock: Lock = field(init=False, repr=False)

    def __init__(self) -> None:
        """Initialize empty in-memory record storage."""
        self._records = {}
        self._lock = Lock()

    def create(self, record: JobRecord) -> None:
        """Persist a new in-memory job record.

        Args:
            record: Job record to persist.
        """
        with self._lock:
            self._records[record.job_id] = record

    def get(self, job_id: str) -> JobRecord | None:
        """Return a job record by ID when present.

        Args:
            job_id: Unique job identifier.
        """
        with self._lock:
            return self._records.get(job_id)

    def update(self, record: JobRecord) -> None:
        """Replace an existing job record.

        Args:
            record: Updated job record.
        """
        with self._lock:
            self._records[record.job_id] = record

    def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        """Replace record only when current status matches expected value."""
        with self._lock:
            current = self._records.get(record.job_id)
            if current is None:
                return False
            if current.status != expected_status:
                return False
            self._records[record.job_id] = record
            return True


@dataclass(slots=True)
class DynamoJobRepository:
    """DynamoDB-backed job record repository."""

    table_name: str
    _table: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize DynamoDB table binding."""
        self._table = boto3.resource("dynamodb").Table(self.table_name)

    def create(self, record: JobRecord) -> None:
        """Persist a new job record."""
        self._table.put_item(Item=_record_to_item(record))

    def get(self, job_id: str) -> JobRecord | None:
        """Return job record by id when present."""
        response = self._table.get_item(Key={"job_id": job_id})
        item = response.get("Item")
        if item is None:
            return None
        return _item_to_record(item)

    def update(self, record: JobRecord) -> None:
        """Replace an existing job record."""
        self._table.put_item(Item=_record_to_item(record))

    def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        """Replace record only when current status matches expected value."""
        try:
            self._table.put_item(
                Item=_record_to_item(record),
                ConditionExpression=(
                    "attribute_exists(job_id) AND #status = :expected_status"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":expected_status": expected_status.value
                },
            )
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code == "ConditionalCheckFailedException":
                return False
            raise
        return True


@dataclass(slots=True)
class MemoryJobPublisher:
    """In-memory queue that can process jobs immediately."""

    process_immediately: bool = True

    def publish(self, *, job: JobRecord) -> None:
        """Publish a job in memory.

        Args:
            job: Job record to publish.
        """
        del job
        return

    def post_publish(
        self,
        *,
        job: JobRecord,
        repository: JobRepository,
        metrics: MetricsCollector,
    ) -> None:
        """Simulate immediate worker execution in local-memory mode."""
        if not self.process_immediately:
            return
        running = job.model_copy(
            update={"status": JobStatus.RUNNING, "updated_at": _utc_now()}
        )
        repository.update(running)
        done = running.model_copy(
            update={
                "status": JobStatus.SUCCEEDED,
                "result": {"accepted": True, "mode": "memory"},
                "updated_at": _utc_now(),
            }
        )
        repository.update(done)
        metrics.incr("jobs_succeeded")


@dataclass(slots=True)
class SqsJobPublisher:
    """SQS-backed queue publisher."""

    queue_url: str
    retry_mode: str = "standard"
    retry_total_max_attempts: int = 3
    _sqs: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the SQS client after dataclass construction."""
        self._sqs = boto3.client(
            "sqs",
            config=Config(
                retries={
                    "mode": self.retry_mode,
                    "total_max_attempts": self.retry_total_max_attempts,
                }
            ),
        )

    def publish(self, *, job: JobRecord) -> None:
        """Publish a job payload to SQS.

        Args:
            job: Job record to send.
        """
        payload = {
            "job_id": job.job_id,
            "job_type": job.job_type,
            "scope_id": job.scope_id,
            "payload": job.payload,
            "created_at": job.created_at.isoformat(),
        }
        try:
            self._sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(
                    payload, separators=(",", ":"), sort_keys=True
                ),
            )
        except ClientError as exc:
            raise JobPublishError(
                details={
                    "error_type": "ClientError",
                    "error_code": str(
                        exc.response.get("Error", {}).get("Code", "Unknown")
                    ),
                }
            ) from exc
        except BotoCoreError as exc:
            raise JobPublishError(
                details={
                    "error_type": type(exc).__name__,
                    "error_code": "BotoCoreError",
                }
            ) from exc

    def post_publish(
        self,
        *,
        job: JobRecord,
        repository: JobRepository,
        metrics: MetricsCollector,
    ) -> None:
        """SQS mode performs work asynchronously; no local follow-up."""
        del job, repository, metrics
        return


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
        """Create and enqueue a job record."""
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
        """Return job by id when owned by caller scope."""
        record = self.repository.get(job_id)
        if record is None:
            raise not_found("job not found")
        if record.scope_id != scope_id:
            raise not_found("job not found")
        return record

    def cancel(self, *, job_id: str, scope_id: str) -> JobRecord:
        """Cancel non-terminal job when owned by caller."""
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
            updated_ok = self.repository.update_if_status(
                record=updated,
                expected_status=record.status,
            )
            if updated_ok:
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

    def update_result(
        self,
        *,
        job_id: str,
        status: JobStatus,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> JobRecord:
        """Update job result/status from worker-side processing."""
        record = self.repository.get(job_id)
        if record is None:
            raise not_found("job not found")
        if not _is_valid_transition(current=record.status, target=status):
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
            queue_lag_ms = _queue_lag_ms(created_at=record.created_at, now=now)
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
        updated_ok = self.repository.update_if_status(
            record=updated,
            expected_status=record.status,
        )
        if not updated_ok:
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


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _queue_lag_ms(*, created_at: datetime, now: datetime) -> float:
    """Calculate queue lag in milliseconds using UTC-safe timestamps."""
    created = (
        created_at
        if created_at.tzinfo is not None
        else created_at.replace(tzinfo=UTC)
    )
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    lag_ms = (current - created).total_seconds() * 1000.0
    return max(0.0, lag_ms)


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


def _is_valid_transition(*, current: JobStatus, target: JobStatus) -> bool:
    """Return whether a status transition is allowed."""
    return target in _ALLOWED_TRANSITIONS[current]


def _record_to_item(record: JobRecord) -> dict[str, Any]:
    """Serialize JobRecord to DynamoDB-friendly item."""
    return record.model_dump(mode="json")


def _item_to_record(item: dict[str, Any]) -> JobRecord:
    """Deserialize DynamoDB item to JobRecord."""
    return JobRecord.model_validate(item)
