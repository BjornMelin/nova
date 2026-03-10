"""Async job APIs and queue abstractions."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Protocol, cast
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.errors import conflict, not_found, queue_unavailable
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import JobRecord, JobStatus


class JobRepository(Protocol):
    """Persist and retrieve job records."""

    async def create(self, record: JobRecord) -> None:
        """Persist a new job record."""

    async def get(self, job_id: str) -> JobRecord | None:
        """
        Retrieve the job record for the given job ID.
        
        Parameters:
            job_id (str): The unique identifier of the job.
        
        Returns:
            JobRecord | None: The JobRecord if present, otherwise None.
        """

    async def update(self, record: JobRecord) -> None:
        """
        Replace the stored job record with the provided JobRecord.
        
        Parameters:
            record (JobRecord): Job record to persist; it will replace any existing record with the same job_id.
        """

    async def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        """
        Attempt to replace the stored job record only when its current status equals the provided expected status.
        
        Parameters:
            record (JobRecord): The new job record to write if the condition matches.
            expected_status (JobStatus): The status value that the existing stored record must have for the replacement to proceed.
        
        Returns:
            bool: `True` if the repository record was replaced, `False` otherwise.
        """

    async def list_for_scope(
        self, *, scope_id: str, limit: int
    ) -> list[JobRecord]:
        """
        List jobs owned by the given scope, ordered newest first.
        
        Args:
            scope_id: Identifier of the caller scope used to filter owned jobs.
            limit: Maximum number of records to return; must be greater than zero.
        
        Returns:
            A list of JobRecord objects belonging to the provided scope ordered by descending creation time (newest first), limited to `limit`.
        
        Raises:
            ValueError: If `limit` is not a positive integer.
        """


class JobPublisher(Protocol):
    """Queue interface for background job dispatch."""

    async def publish(self, *, job: JobRecord) -> None:
        """
        Publish a job record to the backing queue for asynchronous processing.
        
        Parameters:
            job (JobRecord): The job record to enqueue.
        """

    async def post_publish(
        self,
        *,
        job: JobRecord,
        repository: JobRepository,
        metrics: MetricsCollector,
    ) -> None:
        """
        Perform optional post-publish actions after a job is enqueued.
        
        Implementations may update the persisted job record (for example to mark it running or succeeded) and emit metrics or other side effects related to the enqueue operation.
        """

    async def healthcheck(self) -> bool:
        """
        Check whether the backing queue service is reachable and ready.
        
        Returns:
            bool: `True` if the backing queue is reachable and operational, `False` otherwise.
        """


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

    async def create(self, record: JobRecord) -> None:
        """Persist a new in-memory job record.

        Args:
            record: Job record to persist.
        """
        with self._lock:
            self._records[record.job_id] = record

    async def get(self, job_id: str) -> JobRecord | None:
        """
        Retrieve the job record for the given job ID if it exists.
        
        Returns:
            JobRecord | None: The record for the job ID, or `None` if no record is found.
        """
        with self._lock:
            return self._records.get(job_id)

    async def update(self, record: JobRecord) -> None:
        """
        Store the given JobRecord in the in-memory repository, overwriting any existing record with the same job_id.
        
        Parameters:
            record (JobRecord): The job record to store; this will replace any existing entry with the same job_id.
        """
        with self._lock:
            self._records[record.job_id] = record

    async def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        """
        Conditionally replace an existing job record in the in-memory store when its current status equals the expected status.
        
        Parameters:
            record (JobRecord): The new job record to store (replaces the existing record with the same job_id).
            expected_status (JobStatus): The status value that the existing record must have for the replacement to occur.
        
        Returns:
            bool: `True` if the record was replaced; `False` if no existing record was found or its status did not match `expected_status`.
        """
        with self._lock:
            current = self._records.get(record.job_id)
            if current is None:
                return False
            if current.status != expected_status:
                return False
            self._records[record.job_id] = record
            return True

    async def list_for_scope(
        self, *, scope_id: str, limit: int
    ) -> list[JobRecord]:
        """List caller-scoped jobs newest-first.

        Args:
            scope_id: Caller scope identifier used for ownership filtering.
            limit: Maximum number of records to return, newest first.

        Returns:
            list[JobRecord]: Caller-owned records sorted by most recent first.

        Raises:
            ValueError: If ``limit`` is not a positive integer.
        """
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        with self._lock:
            records = [
                r for r in self._records.values() if r.scope_id == scope_id
            ]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]


@dataclass(slots=True)
class DynamoJobRepository:
    """DynamoDB-backed job record repository."""

    table_name: str
    dynamodb_resource: Any
    _table: Any | None = field(init=False, repr=False, default=None)
    _table_lock: asyncio.Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize lazy table resolver."""
        self._table_lock = asyncio.Lock()

    async def create(self, record: JobRecord) -> None:
        """
        Persist the provided JobRecord to the repository's DynamoDB table.
        
        Parameters:
            record (JobRecord): Job record to store; the repository will upsert this record as-is.
        """
        table = await self._resolve_table()
        await table.put_item(Item=_record_to_item(record))

    async def get(self, job_id: str) -> JobRecord | None:
        """
        Retrieve a job record by its ID.
        
        Returns:
            The JobRecord for the given ID, or None if no matching record exists.
        """
        table = await self._resolve_table()
        response = await table.get_item(Key={"job_id": job_id})
        item = response.get("Item")
        if item is None:
            return None
        return _item_to_record(item)

    async def update(self, record: JobRecord) -> None:
        """Replace an existing job record."""
        table = await self._resolve_table()
        await table.put_item(Item=_record_to_item(record))

    async def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        """
        Replace a persisted job record only if the stored job's status equals the provided expected status.
        
        Parameters:
            record: The JobRecord to write.
            expected_status: The JobStatus that the existing stored record must have for the replace to occur.
        
        Returns:
            `true` if the record was replaced, `false` otherwise.
        """
        table = await self._resolve_table()
        try:
            await table.put_item(
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

    async def list_for_scope(
        self, *, scope_id: str, limit: int
    ) -> list[JobRecord]:
        """List caller-scoped jobs newest-first.

        Args:
            scope_id: Caller scope identifier used for ownership filtering.
            limit: Maximum number of records to return, newest first.

        Returns:
            list[JobRecord]: Caller-owned records sorted by most recent first.

        Raises:
            ValueError: If ``limit`` is not a positive integer.
        """
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        items: list[dict[str, Any]] = []
        last_evaluated_key: dict[str, Any] | None = None
        remaining = limit
        table = await self._resolve_table()
        while True:
            query_kwargs: dict[str, Any] = {
                "IndexName": "scope_id-created_at-index",
                "KeyConditionExpression": "#scope_id = :scope_id",
                "ExpressionAttributeNames": {"#scope_id": "scope_id"},
                "ExpressionAttributeValues": {":scope_id": scope_id},
                "Limit": remaining,
                "ScanIndexForward": False,
            }
            if last_evaluated_key is not None:
                query_kwargs["ExclusiveStartKey"] = last_evaluated_key

            try:
                response = await table.query(**query_kwargs)
            except ClientError as exc:
                error = exc.response.get("Error", {})
                error_code = str(error.get("Code", ""))
                error_message = str(error.get("Message", "")).lower()
                if error_code == "ValidationException":
                    if any(
                        keyword in error_message
                        for keyword in (
                            "scope_id-created_at-index",
                            "globalsecondaryindex",
                            "no such index",
                            "index",
                        )
                    ):
                        raise RuntimeError(
                            "jobs table requires the scope_id-created_at-index "
                            "global secondary index for scoped listing"
                        ) from exc
                    raise
                if error_code == "ResourceNotFoundException":
                    raise RuntimeError(
                        "jobs table is not configured for scoped listing"
                    ) from exc
                raise
            items.extend(response.get("Items", []))
            last_evaluated_key = response.get("LastEvaluatedKey")
            remaining = limit - len(items)
            if last_evaluated_key is None or remaining <= 0:
                break
        return [_item_to_record(item) for item in items[:limit]]

    async def _resolve_table(self) -> Any:
        """
        Lazily resolve and cache the DynamoDB table object for this repository.
        
        If the table has not been resolved yet, acquires the internal async lock, initializes and caches the table on the instance; subsequent calls return the cached table.
        
        Returns:
            table (Any): The resolved DynamoDB table object.
        """
        if self._table is not None:
            return self._table
        async with self._table_lock:
            if self._table is None:
                self._table = await self.dynamodb_resource.Table(
                    self.table_name
                )
        return cast(Any, self._table)


@dataclass(slots=True)
class MemoryJobPublisher:
    """In-memory queue that can process jobs immediately."""

    process_immediately: bool = True

    async def publish(self, *, job: JobRecord) -> None:
        """
        Discard the provided JobRecord when publishing to the in-memory queue.
        
        Parameters:
            job (JobRecord): The job to discard; this operation has no external side effects.
        """
        del job
        return

    async def post_publish(
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
        await repository.update(running)
        done = running.model_copy(
            update={
                "status": JobStatus.SUCCEEDED,
                "result": {"accepted": True, "mode": "memory"},
                "updated_at": _utc_now(),
            }
        )
        await repository.update(done)
        metrics.incr("jobs_succeeded")

    async def healthcheck(self) -> bool:
        """
        Check whether the memory-backed publisher is ready.
        
        Returns:
            `True` if the publisher is ready, `False` otherwise.
        """
        return True


@dataclass(slots=True)
class SqsJobPublisher:
    """SQS-backed queue publisher."""

    queue_url: str
    sqs_client: Any

    async def publish(self, *, job: JobRecord) -> None:
        """
        Publish a job to the configured SQS queue.
        
        Serializes the job's identifying fields and payload, sends them as the message body to the publisher's queue URL, and raises a JobPublishError if the underlying SQS client fails.
        
        Parameters:
            job (JobRecord): Job record whose payload will be sent to SQS.
        
        Raises:
            JobPublishError: If the SQS client or underlying boto core experiences an error; the exception's `details` contains `error_type` and `error_code`.
        """
        payload = {
            "job_id": job.job_id,
            "job_type": job.job_type,
            "scope_id": job.scope_id,
            "payload": job.payload,
            "created_at": job.created_at.isoformat(),
        }
        try:
            await self.sqs_client.send_message(
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

    async def post_publish(
        self,
        *,
        job: JobRecord,
        repository: JobRepository,
        metrics: MetricsCollector,
    ) -> None:
        """SQS mode performs work asynchronously; no local follow-up."""
        del job, repository, metrics
        return

    async def healthcheck(self) -> bool:
        """
        Check whether the SQS queue is reachable and its attributes can be retrieved.
        
        Returns:
            `true` if queue attributes could be fetched, `false` otherwise.
        """
        try:
            await self.sqs_client.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=["QueueArn"],
            )
        except (ClientError, BotoCoreError):
            return False
        return True


@dataclass(slots=True)
class JobService:
    """Job orchestration service for enqueue/status/cancel endpoints."""

    repository: JobRepository
    publisher: JobPublisher
    metrics: MetricsCollector

    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        scope_id: str,
    ) -> JobRecord:
        """
        Create a new pending job, persist it, publish it to the queue, and return the stored record.
        
        Creates a JobRecord with the given type, payload, and scope, stores it in the repository, and publishes it via the configured publisher. If publishing fails, the job is marked failed in the repository and a queue_unavailable error is raised. Metrics for enqueue and failed publish are incremented and post-publish hooks are invoked after successful publish.
        
        Parameters:
            job_type (str): Logical type/name of the job to enqueue.
            payload (dict[str, Any]): Arbitrary JSON-serializable payload for the job.
            scope_id (str): Identifier of the owning scope (used for access and listing).
        
        Returns:
            JobRecord: The stored job record (reflecting any repository-updated fields).
        
        Raises:
            queue_unavailable: When the queue publish fails and the job is marked failed.
        """
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
        await self.repository.create(record)
        try:
            await self.publisher.publish(job=record)
        except JobPublishError as exc:
            failed = record.model_copy(
                update={
                    "status": JobStatus.FAILED,
                    "error": "queue_unavailable",
                    "updated_at": _utc_now(),
                }
            )
            await self.repository.update(failed)
            self.metrics.incr("jobs_publish_failed")
            raise queue_unavailable(
                "job enqueue failed because queue publish failed",
                details=exc.details,
            ) from exc

        self.metrics.incr("jobs_enqueued")
        await self.publisher.post_publish(
            job=record,
            repository=self.repository,
            metrics=self.metrics,
        )

        return (await self.repository.get(record.job_id)) or record

    async def get(self, *, job_id: str, scope_id: str) -> JobRecord:
        """
        Retrieve a job by ID if it is owned by the provided scope.
        
        Parameters:
            job_id (str): ID of the job to retrieve.
            scope_id (str): Scope identifier used to verify ownership.
        
        Returns:
            JobRecord: The job record matching the given job_id and scope_id.
        
        Raises:
            Error from `not_found`: If the job does not exist or is not owned by the provided scope.
        """
        record = await self.repository.get(job_id)
        if record is None:
            raise not_found("job not found")
        if record.scope_id != scope_id:
            raise not_found("job not found")
        return record

    async def cancel(self, *, job_id: str, scope_id: str) -> JobRecord:
        """
        Cancel a job owned by the caller if it is not in a terminal state.
        
        If the job is already in a terminal status (SUCCEEDED, FAILED, or CANCELED) the existing record is returned unchanged. The function attempts an atomic status update repeatedly to avoid races; on success it returns the updated record with status set to CANCELED.
        
        Returns:
            JobRecord: The job record after cancellation, or the existing terminal record if no change was necessary.
        
        Raises:
            conflict: If the job could not be canceled after MAX_CANCEL_RETRIES due to concurrent updates.
        """
        for _ in range(MAX_CANCEL_RETRIES):
            record = await self.get(job_id=job_id, scope_id=scope_id)
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
            updated_ok = await self.repository.update_if_status(
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

    async def list_for_scope(
        self, *, scope_id: str, limit: int = 50
    ) -> list[JobRecord]:
        """List jobs for caller scope, newest first.

        Args:
            scope_id: Caller scope identifier used for ownership filtering.
            limit: Maximum number of records to return, newest first.

        Returns:
            list[JobRecord]: Caller-owned records sorted by most recent first.

        Raises:
            ValueError: If ``limit`` is not a positive integer.
        """
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        return await self.repository.list_for_scope(
            scope_id=scope_id, limit=limit
        )

    async def retry(self, *, job_id: str, scope_id: str) -> JobRecord:
        """
        Create a new pending job that re-enqueues a terminal job owned by the caller's scope.
        
        If the source job's status is not FAILED or CANCELED, raises an HTTPException indicating the retry is disallowed.
        
        Returns:
            JobRecord: The newly enqueued pending retry job.
        
        Raises:
            HTTPException: If the source job is not in FAILED or CANCELED state.
        """
        original = await self.get(job_id=job_id, scope_id=scope_id)
        if original.status not in {JobStatus.FAILED, JobStatus.CANCELED}:
            raise conflict(
                "job retry is only allowed from failed or canceled states",
                details={
                    "job_id": job_id,
                    "current_status": original.status.value,
                },
            )
        return await self.enqueue(
            job_type=original.job_type,
            payload=original.payload,
            scope_id=scope_id,
        )

    async def update_result(
        self,
        *,
        job_id: str,
        status: JobStatus,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> JobRecord:
        """
        Apply a worker's processing outcome to a job record, persist the updated status/result, and emit related metrics.
        
        Parameters:
            job_id (str): Identifier of the job to update.
            status (JobStatus): New status to set on the job.
            result (dict[str, Any] | None): Optional result payload produced by the worker.
            error (str | None): Optional error message produced by the worker.
        
        Returns:
            JobRecord: The job record after the update.
        
        Raises:
            NotFoundError: If no job with the given `job_id` exists.
            ConflictError: If the requested status transition is invalid or the record was modified concurrently.
        """
        record = await self.repository.get(job_id)
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
        updated_ok = await self.repository.update_if_status(
            record=updated,
            expected_status=record.status,
        )
        if not updated_ok:
            latest = await self.repository.get(job_id)
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
