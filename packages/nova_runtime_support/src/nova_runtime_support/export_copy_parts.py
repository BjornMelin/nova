"""Persistent export-part state for queue-backed multipart copy workflows."""

from __future__ import annotations

import asyncio
import inspect
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol, cast

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, ConfigDict, Field


class ExportCopyPartStatus(StrEnum):
    """Lifecycle status for one queued export-copy part."""

    QUEUED = "queued"
    COPYING = "copying"
    COPIED = "copied"
    FAILED = "failed"


class ExportCopyPartRecord(BaseModel):
    """Durable state for one queued multipart-copy part."""

    model_config = ConfigDict(extra="forbid")

    export_id: str = Field(min_length=1, max_length=128)
    part_number: int = Field(ge=1, le=10_000)
    source_key: str = Field(min_length=1, max_length=2048)
    export_key: str = Field(min_length=1, max_length=2048)
    upload_id: str = Field(min_length=1, max_length=1024)
    start_byte: int = Field(ge=0)
    end_byte: int = Field(ge=0)
    status: ExportCopyPartStatus
    attempts: int = Field(ge=0, default=0)
    etag: str | None = Field(default=None, min_length=1, max_length=256)
    error: str | None = Field(default=None, max_length=4000)
    created_at: datetime
    updated_at: datetime
    lease_expires_at_epoch: int | None = Field(default=None, ge=1)
    expires_at_epoch: int | None = Field(default=None, ge=1)


class ExportCopyPartRepository(Protocol):
    """Persistence surface used by queued export-copy workers."""

    async def create_many(self, records: list[ExportCopyPartRecord]) -> None:
        """Persist one queued copy manifest."""

    async def get(
        self, *, export_id: str, part_number: int
    ) -> ExportCopyPartRecord | None:
        """Return one queued copy part record."""

    async def list_for_export(
        self, *, export_id: str
    ) -> list[ExportCopyPartRecord]:
        """Return all queued copy parts for one export."""

    async def update(self, record: ExportCopyPartRecord) -> None:
        """Replace one queued copy part record."""

    async def claim(
        self,
        *,
        export_id: str,
        part_number: int,
        upload_id: str,
        source_key: str,
        export_key: str,
    ) -> ExportCopyPartRecord | None:
        """Claim one queued or failed part for copy work."""

    async def mark_copied(
        self, *, export_id: str, part_number: int, etag: str
    ) -> ExportCopyPartRecord | None:
        """Mark one copy part as copied."""

    async def mark_failed(
        self, *, export_id: str, part_number: int, error: str
    ) -> ExportCopyPartRecord | None:
        """Mark one copy part as failed and increment the attempt count."""

    async def healthcheck(self) -> bool:
        """Return whether the repository is ready."""


class DynamoTable(Protocol):
    """Subset of DynamoDB table operations used by copy-part repositories."""

    async def put_item(self, **kwargs: object) -> dict[str, object]:
        """Create or replace one item."""

    async def get_item(self, **kwargs: object) -> dict[str, object]:
        """Read one item."""

    async def query(self, **kwargs: object) -> dict[str, object]:
        """Query items by partition key."""

    async def update_item(self, **kwargs: object) -> dict[str, object]:
        """Apply one conditional item update."""


class DynamoResource(Protocol):
    """Subset of DynamoDB resource operations used by copy-part repositories."""

    def Table(self, table_name: str) -> DynamoTable:
        """Return one table object."""


def export_copy_part_counts(
    records: list[ExportCopyPartRecord],
) -> dict[ExportCopyPartStatus, int]:
    """Return one status-count map for queued copy-part records."""
    counts = Counter(record.status for record in records)
    return {status: counts.get(status, 0) for status in ExportCopyPartStatus}


def completed_parts_payload(
    records: list[ExportCopyPartRecord],
) -> list[dict[str, object]]:
    """Return the completed multipart payload sorted by part number."""
    completed = [
        {
            "ETag": record.etag,
            "PartNumber": record.part_number,
        }
        for record in sorted(records, key=lambda item: item.part_number)
        if record.status == ExportCopyPartStatus.COPIED
        and record.etag is not None
    ]
    return completed


@dataclass(slots=True)
class MemoryExportCopyPartRepository:
    """In-memory export copy-part repository for tests."""

    _records: dict[tuple[str, int], ExportCopyPartRecord] = field(
        default_factory=dict
    )
    claim_lease_seconds: int = 30 * 60
    _lock: asyncio.Lock = field(
        init=False, repr=False, default_factory=asyncio.Lock
    )

    async def create_many(self, records: list[ExportCopyPartRecord]) -> None:
        """Persist one manifest of queued copy-part records in memory."""
        async with self._lock:
            for record in records:
                self._records[(record.export_id, record.part_number)] = record

    async def get(
        self, *, export_id: str, part_number: int
    ) -> ExportCopyPartRecord | None:
        """Return one queued copy-part record from memory."""
        async with self._lock:
            return self._records.get((export_id, part_number))

    async def list_for_export(
        self, *, export_id: str
    ) -> list[ExportCopyPartRecord]:
        """List queued copy-part records for one export from memory."""
        async with self._lock:
            records = [
                record
                for (
                    record_export_id,
                    _part_number,
                ), record in self._records.items()
                if record_export_id == export_id
            ]
        records.sort(key=lambda item: item.part_number)
        return records

    async def update(self, record: ExportCopyPartRecord) -> None:
        """Replace one queued copy-part record in memory."""
        async with self._lock:
            self._records[(record.export_id, record.part_number)] = record

    async def claim(
        self,
        *,
        export_id: str,
        part_number: int,
        upload_id: str,
        source_key: str,
        export_key: str,
    ) -> ExportCopyPartRecord | None:
        """Claim one queued copy-part record for worker execution."""
        async with self._lock:
            current = self._records.get((export_id, part_number))
            if current is None:
                return None
            if (
                current.upload_id != upload_id
                or current.source_key != source_key
                or current.export_key != export_key
            ):
                return None
            if current.status == ExportCopyPartStatus.COPIED:
                return current
            if (
                current.status == ExportCopyPartStatus.COPYING
                and not _lease_expired(
                    lease_expires_at_epoch=current.lease_expires_at_epoch
                )
            ):
                return None
            now = _now_like(current.updated_at)
            updated = current.model_copy(
                update={
                    "status": ExportCopyPartStatus.COPYING,
                    "attempts": current.attempts + 1,
                    "updated_at": now,
                    "lease_expires_at_epoch": _lease_expires_at_epoch(
                        now=now,
                        lease_seconds=self.claim_lease_seconds,
                    ),
                    "error": None,
                }
            )
            self._records[(export_id, part_number)] = updated
            return updated

    async def mark_copied(
        self, *, export_id: str, part_number: int, etag: str
    ) -> ExportCopyPartRecord | None:
        """Mark one queued copy-part record as copied in memory."""
        async with self._lock:
            current = self._records.get((export_id, part_number))
            if current is None:
                return None
            updated = current.model_copy(
                update={
                    "status": ExportCopyPartStatus.COPIED,
                    "etag": etag,
                    "error": None,
                    "updated_at": _now_like(current.updated_at),
                    "lease_expires_at_epoch": None,
                }
            )
            self._records[(export_id, part_number)] = updated
            return updated

    async def mark_failed(
        self, *, export_id: str, part_number: int, error: str
    ) -> ExportCopyPartRecord | None:
        """Mark one queued copy-part record as failed in memory."""
        async with self._lock:
            current = self._records.get((export_id, part_number))
            if current is None:
                return None
            updated = current.model_copy(
                update={
                    "status": ExportCopyPartStatus.FAILED,
                    "error": error,
                    "updated_at": _now_like(current.updated_at),
                    "lease_expires_at_epoch": None,
                }
            )
            self._records[(export_id, part_number)] = updated
            return updated

    async def healthcheck(self) -> bool:
        """Report readiness for the in-memory copy-part repository."""
        return True


@dataclass(slots=True)
class DynamoExportCopyPartRepository:
    """DynamoDB-backed export copy-part repository."""

    table_name: str
    dynamodb_resource: DynamoResource
    claim_lease_seconds: int = 30 * 60
    _table: DynamoTable | None = field(init=False, repr=False, default=None)
    _table_lock: asyncio.Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the lazy DynamoDB table resolver."""
        self._table_lock = asyncio.Lock()

    async def create_many(self, records: list[ExportCopyPartRecord]) -> None:
        """Persist one manifest of queued copy-part records in DynamoDB."""
        table = await self._resolve_table()
        for record in records:
            await table.put_item(Item=_record_to_item(record))

    async def get(
        self, *, export_id: str, part_number: int
    ) -> ExportCopyPartRecord | None:
        """Return one queued copy-part record from DynamoDB."""
        table = await self._resolve_table()
        response = await table.get_item(
            Key={"export_id": export_id, "part_number": part_number}
        )
        item = response.get("Item")
        if item is None:
            return None
        return _item_to_record(cast(dict[str, Any], item))

    async def list_for_export(
        self, *, export_id: str
    ) -> list[ExportCopyPartRecord]:
        """List queued copy-part records for one export from DynamoDB."""
        table = await self._resolve_table()
        response = await table.query(
            KeyConditionExpression="#export_id = :export_id",
            ExpressionAttributeNames={"#export_id": "export_id"},
            ExpressionAttributeValues={":export_id": export_id},
            ScanIndexForward=True,
        )
        items = cast(list[dict[str, Any]], response.get("Items", []))
        return [_item_to_record(item) for item in items]

    async def update(self, record: ExportCopyPartRecord) -> None:
        """Replace one queued copy-part record in DynamoDB."""
        table = await self._resolve_table()
        await table.put_item(Item=_record_to_item(record))

    async def claim(
        self,
        *,
        export_id: str,
        part_number: int,
        upload_id: str,
        source_key: str,
        export_key: str,
    ) -> ExportCopyPartRecord | None:
        """Claim one queued copy-part record for worker execution."""
        table = await self._resolve_table()
        now = datetime.now(tz=UTC)
        now_epoch = int(now.timestamp())
        try:
            response = await table.update_item(
                Key={"export_id": export_id, "part_number": part_number},
                UpdateExpression=(
                    "SET #status = :copying, "
                    "attempts = if_not_exists(attempts, :zero) + :one, "
                    "updated_at = :updated_at, "
                    "lease_expires_at_epoch = :lease_expires_at_epoch "
                    "REMOVE #error"
                ),
                ConditionExpression=(
                    "#upload_id = :upload_id AND "
                    "#source_key = :source_key AND "
                    "#export_key = :export_key AND "
                    "("
                    "#status IN (:queued, :failed) OR "
                    "("
                    "#status = :copying AND "
                    "attribute_exists(lease_expires_at_epoch) AND "
                    "lease_expires_at_epoch <= :now_epoch"
                    ")"
                    ")"
                ),
                ExpressionAttributeNames={
                    "#error": "error",
                    "#export_key": "export_key",
                    "#source_key": "source_key",
                    "#status": "status",
                    "#upload_id": "upload_id",
                },
                ExpressionAttributeValues={
                    ":copying": ExportCopyPartStatus.COPYING.value,
                    ":export_key": export_key,
                    ":failed": ExportCopyPartStatus.FAILED.value,
                    ":lease_expires_at_epoch": now_epoch
                    + self.claim_lease_seconds,
                    ":now_epoch": now_epoch,
                    ":one": 1,
                    ":queued": ExportCopyPartStatus.QUEUED.value,
                    ":source_key": source_key,
                    ":updated_at": now.isoformat(),
                    ":upload_id": upload_id,
                    ":zero": 0,
                },
                ReturnValues="ALL_NEW",
            )
        except ClientError as exc:
            if _is_conditional_check_failed(exc):
                current = await self.get(
                    export_id=export_id,
                    part_number=part_number,
                )
                if current is None:
                    return None
                if current.status == ExportCopyPartStatus.COPIED:
                    return current
                return None
            raise
        attributes = cast(dict[str, Any], response.get("Attributes"))
        return _item_to_record(attributes)

    async def mark_copied(
        self, *, export_id: str, part_number: int, etag: str
    ) -> ExportCopyPartRecord | None:
        """Mark one queued copy-part record as copied in DynamoDB."""
        table = await self._resolve_table()
        now = datetime.now(tz=UTC)
        try:
            response = await table.update_item(
                Key={"export_id": export_id, "part_number": part_number},
                UpdateExpression=(
                    "SET #status = :copied, "
                    "etag = :etag, "
                    "updated_at = :updated_at "
                    "REMOVE #error, lease_expires_at_epoch"
                ),
                ConditionExpression="#status = :copying",
                ExpressionAttributeNames={
                    "#error": "error",
                    "#status": "status",
                },
                ExpressionAttributeValues={
                    ":copied": ExportCopyPartStatus.COPIED.value,
                    ":copying": ExportCopyPartStatus.COPYING.value,
                    ":etag": etag,
                    ":updated_at": now.isoformat(),
                },
                ReturnValues="ALL_NEW",
            )
        except ClientError as exc:
            if _is_conditional_check_failed(exc):
                return await self.get(
                    export_id=export_id,
                    part_number=part_number,
                )
            raise
        attributes = cast(dict[str, Any], response.get("Attributes"))
        return _item_to_record(attributes)

    async def mark_failed(
        self, *, export_id: str, part_number: int, error: str
    ) -> ExportCopyPartRecord | None:
        """Mark one queued copy-part record as failed in DynamoDB."""
        table = await self._resolve_table()
        now = datetime.now(tz=UTC)
        try:
            response = await table.update_item(
                Key={"export_id": export_id, "part_number": part_number},
                UpdateExpression=(
                    "SET #status = :failed, "
                    "#error = :error, "
                    "updated_at = :updated_at "
                    "REMOVE lease_expires_at_epoch"
                ),
                ConditionExpression="#status = :copying",
                ExpressionAttributeNames={
                    "#error": "error",
                    "#status": "status",
                },
                ExpressionAttributeValues={
                    ":copying": ExportCopyPartStatus.COPYING.value,
                    ":error": error,
                    ":failed": ExportCopyPartStatus.FAILED.value,
                    ":updated_at": now.isoformat(),
                },
                ReturnValues="ALL_NEW",
            )
        except ClientError as exc:
            if _is_conditional_check_failed(exc):
                return await self.get(
                    export_id=export_id,
                    part_number=part_number,
                )
            raise
        attributes = cast(dict[str, Any], response.get("Attributes"))
        return _item_to_record(attributes)

    async def healthcheck(self) -> bool:
        """Report readiness for the DynamoDB copy-part repository."""
        try:
            table = await self._resolve_table()
            await table.get_item(
                Key={"export_id": "__health_check__", "part_number": 0}
            )
        except (ClientError, BotoCoreError):
            return False
        return True

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


def build_export_copy_part_repository(
    *,
    table_name: str | None,
    dynamodb_resource: DynamoResource | None,
    enabled: bool,
    claim_lease_seconds: int = 30 * 60,
) -> ExportCopyPartRepository:
    """Return the configured copy-part repository."""
    normalized_table_name = (table_name or "").strip()
    if enabled:
        if not normalized_table_name:
            raise ValueError(
                "FILE_TRANSFER_EXPORT_COPY_PARTS_TABLE must be configured when "
                "queued export copy is enabled"
            )
        if dynamodb_resource is None:
            raise ValueError(
                "dynamodb resource is required when queued export copy "
                "is enabled"
            )
        return DynamoExportCopyPartRepository(
            table_name=normalized_table_name,
            dynamodb_resource=dynamodb_resource,
            claim_lease_seconds=claim_lease_seconds,
        )
    return MemoryExportCopyPartRepository(
        claim_lease_seconds=claim_lease_seconds
    )


def _record_to_item(record: ExportCopyPartRecord) -> dict[str, object]:
    return cast(dict[str, object], record.model_dump(mode="json"))


def _item_to_record(item: dict[str, Any]) -> ExportCopyPartRecord:
    normalized = dict(item)
    part_number = normalized.get("part_number")
    expires_at_epoch = normalized.get("expires_at_epoch")
    lease_expires_at_epoch = normalized.get("lease_expires_at_epoch")
    if isinstance(part_number, Decimal):
        normalized["part_number"] = int(part_number)
    if isinstance(expires_at_epoch, Decimal):
        normalized["expires_at_epoch"] = int(expires_at_epoch)
    if isinstance(lease_expires_at_epoch, Decimal):
        normalized["lease_expires_at_epoch"] = int(lease_expires_at_epoch)
    return ExportCopyPartRecord.model_validate(normalized)


def _as_dynamo_table(table: object) -> DynamoTable:
    invalid_methods: list[str] = []
    for method_name in ("put_item", "get_item", "query", "update_item"):
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


def _now_like(value: datetime) -> datetime:
    tzinfo = value.tzinfo or UTC
    return datetime.now(tz=tzinfo)


def _is_conditional_check_failed(exc: ClientError) -> bool:
    error_code = str(exc.response.get("Error", {}).get("Code", ""))
    return error_code == "ConditionalCheckFailedException"


def _lease_expired(*, lease_expires_at_epoch: int | None) -> bool:
    if lease_expires_at_epoch is None:
        return False
    return lease_expires_at_epoch <= int(datetime.now(tz=UTC).timestamp())


def _lease_expires_at_epoch(*, now: datetime, lease_seconds: int) -> int:
    return int(now.timestamp()) + lease_seconds
