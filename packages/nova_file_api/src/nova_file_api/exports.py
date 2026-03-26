"""Export workflow services and queue abstractions."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.errors import conflict, not_found, queue_unavailable
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import ExportOutput, ExportRecord, ExportStatus

JsonObject = dict[str, object]


class ExportRepository(Protocol):
    """Persist and retrieve export workflow records."""

    async def create(self, record: ExportRecord) -> None:
        """Persist a new export record."""

    async def get(self, export_id: str) -> ExportRecord | None:
        """Return export record by id if present."""

    async def update(self, record: ExportRecord) -> None:
        """Replace an export record."""

    async def update_if_status(
        self,
        *,
        record: ExportRecord,
        expected_status: ExportStatus,
    ) -> bool:
        """Replace record only when current status matches expected value."""

    async def list_for_scope(
        self, *, scope_id: str, limit: int
    ) -> list[ExportRecord]:
        """List exports visible to the provided caller scope."""

    async def healthcheck(self) -> bool:
        """Return readiness of the backing storage dependency."""


class ExportPublisher(Protocol):
    """Queue interface for background export dispatch."""

    async def publish(self, *, export: ExportRecord) -> None:
        """Publish export record to background queue."""

    async def post_publish(
        self,
        *,
        export: ExportRecord,
        repository: ExportRepository,
        metrics: MetricsCollector,
    ) -> None:
        """Run optional post-publish handling."""

    async def healthcheck(self) -> bool:
        """Return readiness of the backing queue dependency."""


class DynamoTable(Protocol):
    """Subset of DynamoDB table operations used by repositories."""

    async def put_item(self, **kwargs: object) -> Mapping[str, object]:
        """Create or replace an item."""

    async def get_item(self, **kwargs: object) -> Mapping[str, object]:
        """Read a single item by key."""

    async def query(self, **kwargs: object) -> Mapping[str, object]:
        """Query items using a secondary index."""


class DynamoResource(Protocol):
    """Subset of DynamoDB resource operations used by repositories."""

    def Table(self, table_name: str) -> DynamoTable | Awaitable[DynamoTable]:
        """Return table object or awaitable table object."""


class SqsClient(Protocol):
    """Subset of SQS client operations used by publishers."""

    async def send_message(self, **kwargs: object) -> Mapping[str, object]:
        """Publish a queue message."""

    async def get_queue_attributes(
        self, **kwargs: object
    ) -> Mapping[str, object]:
        """Read queue attributes for health checks."""


def _as_dynamo_table(table: object) -> DynamoTable:
    """Validate and cast a DynamoDB table-like object."""
    invalid_methods: list[str] = []
    for method_name in ("put_item", "get_item", "query"):
        method = getattr(table, method_name, None)
        if not callable(method):
            invalid_methods.append(method_name)
    if invalid_methods:
        methods = ", ".join(invalid_methods)
        raise TypeError(
            "dynamodb resource returned an invalid table object; "
            f"missing or non-callable: {methods}"
        )
    return cast(DynamoTable, table)


@dataclass(slots=True)
class ExportPublishError(Exception):
    """Raised when queue publish fails and export creation cannot proceed."""

    details: dict[str, str]

    def __post_init__(self) -> None:
        """Seed a stable Exception message for logging surfaces."""
        Exception.__init__(self, "queue publish failed")


@dataclass(slots=True)
class MemoryExportRepository:
    """In-memory export record repository."""

    _records: dict[str, ExportRecord]
    _lock: asyncio.Lock = field(init=False, repr=False)

    def __init__(self) -> None:
        """Initialize empty in-memory record storage."""
        self._records = {}
        self._lock = asyncio.Lock()

    async def create(self, record: ExportRecord) -> None:
        """Persist a new in-memory export record."""
        async with self._lock:
            self._records[record.export_id] = record

    async def get(self, export_id: str) -> ExportRecord | None:
        """Return an export record by id when present."""
        async with self._lock:
            return self._records.get(export_id)

    async def update(self, record: ExportRecord) -> None:
        """Replace an existing export record."""
        async with self._lock:
            self._records[record.export_id] = record

    async def update_if_status(
        self,
        *,
        record: ExportRecord,
        expected_status: ExportStatus,
    ) -> bool:
        """Replace record only when current status matches expected value."""
        async with self._lock:
            current = self._records.get(record.export_id)
            if current is None or current.status != expected_status:
                return False
            self._records[record.export_id] = record
            return True

    async def list_for_scope(
        self, *, scope_id: str, limit: int
    ) -> list[ExportRecord]:
        """List caller-scoped exports newest-first."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        async with self._lock:
            records = [
                record
                for record in self._records.values()
                if record.scope_id == scope_id
            ]
        records.sort(key=lambda record: record.created_at, reverse=True)
        return records[:limit]

    async def healthcheck(self) -> bool:
        """Report readiness for in-memory storage."""
        return True


@dataclass(slots=True)
class DynamoExportRepository:
    """DynamoDB-backed export record repository."""

    table_name: str
    dynamodb_resource: DynamoResource
    _table: DynamoTable | None = field(init=False, repr=False, default=None)
    _table_lock: asyncio.Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the lazy table resolver."""
        self._table_lock = asyncio.Lock()

    async def create(self, record: ExportRecord) -> None:
        """Persist a new export record."""
        table = await self._resolve_table()
        await table.put_item(Item=_record_to_item(record))

    async def get(self, export_id: str) -> ExportRecord | None:
        """Return an export record by id when present."""
        table = await self._resolve_table()
        response = await table.get_item(Key={"export_id": export_id})
        item = response.get("Item")
        if item is None:
            return None
        return _item_to_record(cast(JsonObject, item))

    async def update(self, record: ExportRecord) -> None:
        """Replace an existing export record."""
        table = await self._resolve_table()
        await table.put_item(Item=_record_to_item(record))

    async def update_if_status(
        self,
        *,
        record: ExportRecord,
        expected_status: ExportStatus,
    ) -> bool:
        """Replace record only when current status matches expected value."""
        table = await self._resolve_table()
        try:
            await table.put_item(
                Item=_record_to_item(record),
                ConditionExpression=(
                    "attribute_exists(export_id) AND #status = :expected_status"
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
    ) -> list[ExportRecord]:
        """List caller-scoped exports newest-first."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        items: list[JsonObject] = []
        last_evaluated_key: JsonObject | None = None
        remaining = limit
        table = await self._resolve_table()
        while True:
            query_kwargs: dict[str, object] = {
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
                            "exports table requires the "
                            "scope_id-created_at-index global secondary "
                            "index for scoped listing"
                        ) from exc
                    raise
                if error_code == "ResourceNotFoundException":
                    raise RuntimeError(
                        "exports table is not configured for scoped listing"
                    ) from exc
                raise
            items.extend(cast(list[JsonObject], response.get("Items", [])))
            last_evaluated_key = cast(
                JsonObject | None, response.get("LastEvaluatedKey")
            )
            remaining = limit - len(items)
            if last_evaluated_key is None or remaining <= 0:
                break
        return [_item_to_record(item) for item in items[:limit]]

    async def _resolve_table(self) -> DynamoTable:
        if self._table is not None:
            return self._table
        async with self._table_lock:
            if self._table is None:
                table_obj = self.dynamodb_resource.Table(self.table_name)
                if inspect.isawaitable(table_obj):
                    table_obj = await table_obj
                self._table = _as_dynamo_table(table_obj)
        assert self._table is not None
        return self._table

    async def healthcheck(self) -> bool:
        """Return True when the DynamoDB table is reachable."""
        try:
            table = await self._resolve_table()
            await table.get_item(Key={"export_id": "__health_check__"})
        except (ClientError, BotoCoreError):
            return False
        return True


@dataclass(slots=True)
class MemoryExportPublisher:
    """In-memory queue that can process exports immediately."""

    export_prefix: str = "exports/"
    process_immediately: bool = True

    async def publish(self, *, export: ExportRecord) -> None:
        """Publish an export in memory."""
        del export
        return

    async def post_publish(
        self,
        *,
        export: ExportRecord,
        repository: ExportRepository,
        metrics: MetricsCollector,
    ) -> None:
        """Simulate immediate export completion in local-memory mode."""
        if not self.process_immediately:
            return
        validating = export.model_copy(
            update={
                "status": ExportStatus.VALIDATING,
                "updated_at": _utc_now(),
            }
        )
        await repository.update(validating)
        copying = validating.model_copy(
            update={
                "status": ExportStatus.COPYING,
                "updated_at": _utc_now(),
            }
        )
        await repository.update(copying)
        output = ExportOutput(
            key=_export_object_key(
                export=copying,
                export_prefix=self.export_prefix,
            ),
            download_filename=copying.filename,
        )
        finalizing = copying.model_copy(
            update={
                "status": ExportStatus.FINALIZING,
                "output": output,
                "updated_at": _utc_now(),
            }
        )
        await repository.update(finalizing)
        done = finalizing.model_copy(
            update={
                "status": ExportStatus.SUCCEEDED,
                "updated_at": _utc_now(),
            }
        )
        await repository.update(done)
        metrics.incr("exports_succeeded")

    async def healthcheck(self) -> bool:
        """Return readiness for the memory-backed publisher."""
        return True


@dataclass(slots=True)
class SqsExportPublisher:
    """SQS-backed queue publisher."""

    queue_url: str
    sqs_client: SqsClient

    async def publish(self, *, export: ExportRecord) -> None:
        """Publish an export payload to SQS."""
        payload = {
            "export_id": export.export_id,
            "scope_id": export.scope_id,
            "source_key": export.source_key,
            "filename": export.filename,
            "created_at": export.created_at.isoformat(),
        }
        try:
            await self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(
                    payload, separators=(",", ":"), sort_keys=True
                ),
            )
        except ClientError as exc:
            raise ExportPublishError(
                details={
                    "error_type": "ClientError",
                    "error_code": str(
                        exc.response.get("Error", {}).get("Code", "Unknown")
                    ),
                }
            ) from exc
        except BotoCoreError as exc:
            raise ExportPublishError(
                details={
                    "error_type": type(exc).__name__,
                    "error_code": "BotoCoreError",
                }
            ) from exc

    async def post_publish(
        self,
        *,
        export: ExportRecord,
        repository: ExportRepository,
        metrics: MetricsCollector,
    ) -> None:
        """SQS mode performs work asynchronously with no local follow-up."""
        del export, repository, metrics
        return

    async def healthcheck(self) -> bool:
        """Return whether queue metadata can be fetched successfully."""
        try:
            await self.sqs_client.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=["QueueArn"],
            )
        except (ClientError, BotoCoreError):
            return False
        return True


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
        """Update export output/status from worker-side processing."""
        record = await self.repository.get(export_id)
        if record is None:
            raise not_found("export not found")
        if not _is_valid_transition(current=record.status, target=status):
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
        queue_lag_ms: float | None = None
        if (
            record.status == ExportStatus.QUEUED
            and status != ExportStatus.QUEUED
        ):
            queue_lag_ms = _queue_lag_ms(created_at=record.created_at, now=now)
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

        if queue_lag_ms is not None:
            self.metrics.observe_ms("exports_queue_lag_ms", queue_lag_ms)
            self.metrics.emit_emf(
                metric_name="exports_queue_lag_ms",
                value=queue_lag_ms,
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


_ALLOWED_TRANSITIONS: dict[ExportStatus, set[ExportStatus]] = {
    ExportStatus.QUEUED: {
        ExportStatus.QUEUED,
        ExportStatus.VALIDATING,
        ExportStatus.FAILED,
        ExportStatus.CANCELLED,
    },
    ExportStatus.VALIDATING: {
        ExportStatus.VALIDATING,
        ExportStatus.COPYING,
        ExportStatus.FAILED,
        ExportStatus.CANCELLED,
    },
    ExportStatus.COPYING: {
        ExportStatus.COPYING,
        ExportStatus.FINALIZING,
        ExportStatus.FAILED,
        ExportStatus.CANCELLED,
    },
    ExportStatus.FINALIZING: {
        ExportStatus.FINALIZING,
        ExportStatus.SUCCEEDED,
        ExportStatus.FAILED,
        ExportStatus.CANCELLED,
    },
    ExportStatus.SUCCEEDED: {ExportStatus.SUCCEEDED},
    ExportStatus.FAILED: {ExportStatus.FAILED},
    ExportStatus.CANCELLED: {ExportStatus.CANCELLED},
}
MAX_CANCEL_RETRIES = 8


def _is_valid_transition(
    *, current: ExportStatus, target: ExportStatus
) -> bool:
    """Return whether a status transition is allowed."""
    return target in _ALLOWED_TRANSITIONS[current]


def _export_object_key(
    *,
    export: ExportRecord,
    export_prefix: str,
) -> str:
    normalized_prefix = export_prefix.strip().strip("/") or "exports"
    return (
        f"{normalized_prefix}/{export.scope_id}/"
        f"{export.export_id}/{export.filename}"
    )


def _record_to_item(record: ExportRecord) -> JsonObject:
    """Serialize ExportRecord to DynamoDB-friendly item."""
    return cast(JsonObject, record.model_dump(mode="json"))


def _item_to_record(item: JsonObject) -> ExportRecord:
    """Deserialize DynamoDB item to ExportRecord."""
    return ExportRecord.model_validate(item)
