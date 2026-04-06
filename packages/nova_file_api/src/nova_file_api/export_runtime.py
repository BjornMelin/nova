"""Shared export runtime repositories, publishers, and status transitions."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections.abc import Awaitable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, cast

from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.export_models import (
    ExportOutput,
    ExportRecord,
    ExportStatus,
)

JsonObject = dict[str, object]


class ExportMetrics(Protocol):
    """Minimal metrics surface used by export runtime helpers."""

    def incr(self, key: str, value: int = 1) -> None:
        """Increment counter by value."""

    def observe_ms(self, key: str, value_ms: float) -> None:
        """Record latency metric in milliseconds."""

    def emit_emf(
        self,
        *,
        metric_name: str,
        value: float,
        unit: str,
        dimensions: dict[str, str],
    ) -> None:
        """Emit structured EMF metric."""


@dataclass(slots=True)
class NoopExportMetrics:
    """Metrics sink used when workflow handlers do not need EMF output."""

    def incr(self, key: str, value: int = 1) -> None:
        """Discard counter increments."""
        del key, value

    def observe_ms(self, key: str, value_ms: float) -> None:
        """Discard latency observations."""
        del key, value_ms

    def emit_emf(
        self,
        *,
        metric_name: str,
        value: float,
        unit: str,
        dimensions: dict[str, str],
    ) -> None:
        """Discard EMF payloads."""
        del metric_name, value, unit, dimensions


@dataclass(slots=True)
class ExportStatusLookupError(LookupError):
    """Raised when an export record is missing during status updates."""

    export_id: str

    def __post_init__(self) -> None:
        """Populate a stable exception message for adapters."""
        Exception.__init__(self, "export not found")


@dataclass(slots=True)
class ExportStatusTransitionError(ValueError):
    """Raised when an export status transition is invalid."""

    export_id: str
    requested_status: ExportStatus
    current_status: ExportStatus | None = None

    def __post_init__(self) -> None:
        """Populate a stable exception message for adapters."""
        Exception.__init__(self, "invalid export state transition")


class ExportStatusOutputRequiredError(ValueError):
    """Raised when a succeeded export transition lacks output."""

    def __init__(self) -> None:
        """Populate a stable exception message for adapters."""
        super().__init__("export output is required for succeeded status")


class ExportRepository(Protocol):
    """Persist and retrieve export workflow records."""

    async def create(self, record: ExportRecord) -> None:
        """Persist a new export record."""

    async def get(self, export_id: str) -> ExportRecord | None:
        """Return one export by primary key with strong read semantics."""

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
        """List exports visible to the provided caller scope.

        This path is GSI-backed and therefore eventually consistent.
        """

    async def healthcheck(self) -> bool:
        """Return readiness of the backing storage dependency."""


class ExportPublisher(Protocol):
    """Queue interface for background export dispatch."""

    async def publish(self, *, export: ExportRecord) -> str | None:
        """Publish an export record to the workflow backend.

        Args:
            export: Export resource to enqueue for background processing.

        Returns:
            The workflow execution identifier when the backend provides one;
            otherwise ``None``.

        Raises:
            ExportPublishError: Raised when the backend rejects the publish
                request or returns an invalid response.
        """

    async def stop_execution(self, *, execution_arn: str, cause: str) -> None:
        """Stop a running workflow execution when canceling.

        Args:
            execution_arn: Workflow execution ARN to stop.
            cause: Human-readable cancellation reason sent to the backend.

        Returns:
            None.

        Raises:
            ClientError: Raised when the workflow backend rejects the stop
                request.
            BotoCoreError: Raised when the AWS client transport fails.
        """

    async def post_publish(
        self,
        *,
        export: ExportRecord,
        repository: ExportRepository,
        metrics: ExportMetrics,
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


class StepFunctionsClient(Protocol):
    """Subset of Step Functions client operations used by publishers."""

    async def start_execution(self, **kwargs: object) -> Mapping[str, object]:
        """Start a workflow execution."""

    async def stop_execution(self, **kwargs: object) -> Mapping[str, object]:
        """Stop a workflow execution.

        Args:
            **kwargs: Keyword arguments forwarded to the Step Functions client.

        Returns:
            The service response mapping returned by the client.

        Raises:
            ClientError: Raised when the AWS service rejects the request.
            BotoCoreError: Raised when the AWS client transport fails.
        """

    async def describe_state_machine(
        self, **kwargs: object
    ) -> Mapping[str, object]:
        """Read state machine metadata for health checks."""


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
    """Raised when workflow dispatch fails after record creation."""

    details: dict[str, str]

    def __post_init__(self) -> None:
        """Seed a stable exception message for logging surfaces."""
        Exception.__init__(self, "export publish failed")


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
        """Replace a record only when its current status matches."""
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
        """Initialize the lazy DynamoDB table resolver."""
        self._table_lock = asyncio.Lock()

    async def create(self, record: ExportRecord) -> None:
        """Persist a new export record."""
        table = await self._resolve_table()
        await table.put_item(Item=_record_to_item(record))

    async def get(self, export_id: str) -> ExportRecord | None:
        """Return an export record by id when present."""
        table = await self._resolve_table()
        response = await table.get_item(
            Key={"export_id": export_id},
            ConsistentRead=True,
        )
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
        """Replace a record only when its current status matches."""
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
        """List caller-scoped exports newest-first via the eventual GSI."""
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
        """Return whether the DynamoDB table is reachable."""
        try:
            table = await self._resolve_table()
            await table.get_item(
                Key={"export_id": "__health_check__"},
                ConsistentRead=True,
            )
        except (ClientError, BotoCoreError):
            return False
        return True


@dataclass(slots=True)
class MemoryExportPublisher:
    """In-memory queue that can process exports immediately."""

    export_prefix: str = "exports/"
    process_immediately: bool = True

    async def publish(self, *, export: ExportRecord) -> str | None:
        """Publish an export in memory.

        Args:
            export: Export record to simulate publishing.

        Returns:
            ``None`` because in-memory publishing does not allocate an
            execution identifier.

        Raises:
            None.
        """
        del export
        return None

    async def stop_execution(self, *, execution_arn: str, cause: str) -> None:
        """Ignore stop requests in memory mode.

        Args:
            execution_arn: Ignored execution ARN for the in-memory backend.
            cause: Ignored cancellation reason for the in-memory backend.

        Returns:
            None.

        Raises:
            None.
        """
        del execution_arn, cause

    async def post_publish(
        self,
        *,
        export: ExportRecord,
        repository: ExportRepository,
        metrics: ExportMetrics,
    ) -> None:
        """Simulate immediate export completion for local-memory mode."""
        if not self.process_immediately:
            return
        validating = export.model_copy(
            update={"status": ExportStatus.VALIDATING, "updated_at": _utc_now()}
        )
        await repository.update(validating)
        copying_entered_at = _utc_now()
        copying = validating.model_copy(
            update={
                "status": ExportStatus.COPYING,
                "updated_at": copying_entered_at,
                "copying_entered_at": copying_entered_at,
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
        finalizing_entered_at = _utc_now()
        finalizing = copying.model_copy(
            update={
                "status": ExportStatus.FINALIZING,
                "output": output,
                "updated_at": finalizing_entered_at,
                "finalizing_entered_at": finalizing_entered_at,
            }
        )
        await repository.update(finalizing)
        done = finalizing.model_copy(
            update={"status": ExportStatus.SUCCEEDED, "updated_at": _utc_now()}
        )
        await repository.update(done)
        metrics.incr("exports_succeeded")

    async def healthcheck(self) -> bool:
        """Report readiness for the memory-backed publisher."""
        return True


@dataclass(slots=True)
class StepFunctionsExportPublisher:
    """Step Functions-backed workflow dispatcher."""

    state_machine_arn: str
    stepfunctions_client: StepFunctionsClient
    _logger: logging.Logger = field(
        init=False,
        repr=False,
        default_factory=lambda: logging.getLogger(__name__),
    )

    async def publish(self, *, export: ExportRecord) -> str:
        """Start a Step Functions execution for the export.

        Args:
            export: Export record to dispatch to Step Functions.

        Returns:
            The execution ARN returned by Step Functions.

        Raises:
            ExportPublishError: Raised when Step Functions rejects the request
                or omits the execution ARN from the response.
        """
        payload = {
            "export_id": export.export_id,
            "scope_id": export.scope_id,
            "source_key": export.source_key,
            "filename": export.filename,
            "request_id": export.request_id,
            "status": export.status.value,
            "execution_arn": export.execution_arn,
            "cancel_requested_at": (
                export.cancel_requested_at.isoformat()
                if export.cancel_requested_at is not None
                else None
            ),
            "source_size_bytes": export.source_size_bytes,
            "copy_strategy": export.copy_strategy,
            "copy_export_key": export.copy_export_key,
            "copy_upload_id": export.copy_upload_id,
            "copy_part_size_bytes": export.copy_part_size_bytes,
            "copy_part_count": export.copy_part_count,
            "created_at": export.created_at.isoformat(),
            "updated_at": export.updated_at.isoformat(),
            "copying_entered_at": (
                export.copying_entered_at.isoformat()
                if export.copying_entered_at is not None
                else None
            ),
            "finalizing_entered_at": (
                export.finalizing_entered_at.isoformat()
                if export.finalizing_entered_at is not None
                else None
            ),
        }
        try:
            response = await self.stepfunctions_client.start_execution(
                stateMachineArn=self.state_machine_arn,
                name=export.export_id,
                input=json.dumps(
                    payload,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )
            execution_arn = _opt_str(response.get("executionArn"))
            if execution_arn is None:
                raise ExportPublishError(
                    details={
                        "error_type": "ResponseValidationError",
                        "error_code": "MissingExecutionArn",
                    }
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
        else:
            return execution_arn

    async def post_publish(
        self,
        *,
        export: ExportRecord,
        repository: ExportRepository,
        metrics: ExportMetrics,
    ) -> None:
        """Skip local follow-up for asynchronous workflow dispatch."""
        del export, repository, metrics

    async def stop_execution(self, *, execution_arn: str, cause: str) -> None:
        """Stop the workflow execution backing a canceled export.

        Args:
            execution_arn: Workflow execution ARN to stop.
            cause: Human-readable reason sent to Step Functions.

        Returns:
            None.

        Raises:
            ClientError: Raised when Step Functions rejects the stop request
                for reasons other than a missing execution.
            BotoCoreError: Raised when the AWS client transport fails.
        """
        try:
            await self.stepfunctions_client.stop_execution(
                executionArn=execution_arn,
                cause=cause,
            )
        except ClientError as exc:
            error_code = str(
                exc.response.get("Error", {}).get("Code", "Unknown")
            )
            if error_code != "ExecutionDoesNotExist":
                raise
            self._logger.debug(
                "stop_execution_suppressed",
                extra={
                    "execution_arn": execution_arn,
                    "cause": cause,
                    "error_code": error_code,
                },
            )
            return

    async def healthcheck(self) -> bool:
        """Return whether the state machine metadata can be fetched."""
        try:
            await self.stepfunctions_client.describe_state_machine(
                stateMachineArn=self.state_machine_arn
            )
        except (ClientError, BotoCoreError):
            return False
        return True


@dataclass(slots=True)
class WorkflowExportStateService:
    """Shared workflow-side export status updater."""

    repository: ExportRepository
    metrics: ExportMetrics = field(default_factory=NoopExportMetrics)

    async def update_status(
        self,
        *,
        export_id: str,
        status: ExportStatus,
        output: ExportOutput | None = None,
        error: str | None = None,
    ) -> ExportRecord:
        """Persist a workflow-side export status transition."""
        return await update_export_status_shared(
            repository=self.repository,
            metrics=self.metrics,
            export_id=export_id,
            status=status,
            output=output,
            error=error,
        )


def utc_now() -> datetime:
    """Return timezone-aware UTC now for export runtime callers."""
    return _utc_now()


def queue_lag_ms(*, created_at: datetime, now: datetime) -> float:
    """Return queue lag in milliseconds for export runtime callers."""
    return _queue_lag_ms(created_at=created_at, now=now)


def export_status_transition_allowed(
    *, current: ExportStatus, target: ExportStatus
) -> bool:
    """Return whether a status transition is allowed."""
    return _is_valid_transition(current=current, target=target)


def export_record_to_item(record: ExportRecord) -> JsonObject:
    """Serialize an export record to a DynamoDB-friendly item."""
    return _record_to_item(record)


def item_to_export_record(item: JsonObject) -> ExportRecord:
    """Deserialize a DynamoDB item payload into an export record."""
    return _item_to_record(item)


def export_object_key(
    *,
    export: ExportRecord,
    export_prefix: str,
) -> str:
    """Return the storage key used for memory-mode export completion."""
    return _export_object_key(export=export, export_prefix=export_prefix)


async def update_export_status_shared(
    *,
    repository: ExportRepository,
    metrics: ExportMetrics,
    export_id: str,
    status: ExportStatus,
    output: ExportOutput | None = None,
    error: str | None = None,
) -> ExportRecord:
    """Persist a status transition with shared validation and metrics."""
    record = await repository.get(export_id)
    if record is None:
        raise ExportStatusLookupError(export_id=export_id)
    if not _is_valid_transition(current=record.status, target=status):
        raise ExportStatusTransitionError(
            export_id=export_id,
            current_status=record.status,
            requested_status=status,
        )

    now = _utc_now()
    update_payload: dict[str, object] = {
        "status": status,
    }
    if status != record.status:
        update_payload["updated_at"] = now
    queue_lag_ms: float | None = None
    copying_age_ms: float | None = None
    finalizing_age_ms: float | None = None
    if status == ExportStatus.COPYING and record.status != ExportStatus.COPYING:
        update_payload["copying_entered_at"] = now
    if (
        status == ExportStatus.FINALIZING
        and record.status != ExportStatus.FINALIZING
    ):
        update_payload["finalizing_entered_at"] = now
    if record.status == ExportStatus.QUEUED and status != ExportStatus.QUEUED:
        queue_lag_ms = _queue_lag_ms(created_at=record.created_at, now=now)
    if record.status == ExportStatus.COPYING and status != ExportStatus.COPYING:
        copying_age_ms = _stage_age_ms(
            started_at=record.copying_entered_at or record.updated_at,
            now=now,
        )
    if (
        record.status == ExportStatus.FINALIZING
        and status != ExportStatus.FINALIZING
    ):
        finalizing_age_ms = _stage_age_ms(
            started_at=record.finalizing_entered_at or record.updated_at,
            now=now,
        )
    if output is not None:
        update_payload["output"] = output
    if error is not None:
        update_payload["error"] = error
    if status == ExportStatus.SUCCEEDED:
        if output is None and record.output is None:
            raise ExportStatusOutputRequiredError()
        update_payload["output"] = output or record.output
        update_payload["error"] = None
    if status == ExportStatus.FAILED and error is None:
        update_payload["error"] = record.error or "export_failed"

    updated = record.model_copy(update=update_payload)
    updated_ok = await repository.update_if_status(
        record=updated,
        expected_status=record.status,
    )
    if not updated_ok:
        latest = await repository.get(export_id)
        if latest is None:
            raise ExportStatusLookupError(export_id=export_id)
        if latest.status == status:
            return latest
        raise ExportStatusTransitionError(
            export_id=export_id,
            current_status=latest.status,
            requested_status=status,
        )

    if queue_lag_ms is not None:
        metrics.observe_ms("exports_queue_lag_ms", queue_lag_ms)
        metrics.emit_emf(
            metric_name="exports_queue_lag_ms",
            value=queue_lag_ms,
            unit="Milliseconds",
            dimensions={"source": "export_status_update"},
        )
        metrics.observe_ms("exports_queued_age_ms", queue_lag_ms)
        metrics.emit_emf(
            metric_name="exports_queued_age_ms",
            value=queue_lag_ms,
            unit="Milliseconds",
            dimensions={"source": "export_status_update"},
        )
    if copying_age_ms is not None:
        metrics.observe_ms("exports_copying_age_ms", copying_age_ms)
        metrics.emit_emf(
            metric_name="exports_copying_age_ms",
            value=copying_age_ms,
            unit="Milliseconds",
            dimensions={"source": "export_status_update"},
        )
    if finalizing_age_ms is not None:
        metrics.observe_ms("exports_finalizing_age_ms", finalizing_age_ms)
        metrics.emit_emf(
            metric_name="exports_finalizing_age_ms",
            value=finalizing_age_ms,
            unit="Milliseconds",
            dimensions={"source": "export_status_update"},
        )
    metrics.incr(f"exports_{status.value}")
    metrics.incr("exports_status_updates_total")
    metrics.incr(f"exports_status_updates_{status.value}")
    metrics.emit_emf(
        metric_name="exports_status_updates_total",
        value=1,
        unit="Count",
        dimensions={"status": status.value},
    )
    return updated


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _queue_lag_ms(*, created_at: datetime, now: datetime) -> float:
    created = (
        created_at
        if created_at.tzinfo is not None
        else created_at.replace(tzinfo=UTC)
    )
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    lag_ms = (current - created).total_seconds() * 1000.0
    return max(0.0, lag_ms)


def _stage_age_ms(*, started_at: datetime, now: datetime) -> float:
    updated = (
        started_at
        if started_at.tzinfo is not None
        else started_at.replace(tzinfo=UTC)
    )
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    age_ms = (current - updated).total_seconds() * 1000.0
    return max(0.0, age_ms)


def _opt_str(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


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


def _is_valid_transition(
    *, current: ExportStatus, target: ExportStatus
) -> bool:
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
    return cast(JsonObject, record.model_dump(mode="json"))


def _item_to_record(item: JsonObject) -> ExportRecord:
    return ExportRecord.model_validate(item)
