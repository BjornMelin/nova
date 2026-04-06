"""Upload session persistence for direct-to-S3 transfers."""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol, cast
from uuid import uuid4

from boto3.dynamodb.types import TypeSerializer  # type: ignore[import-untyped]
from botocore.exceptions import BotoCoreError, ClientError

_ALLOWED_UPLOAD_SESSION_CHECKSUM_MODES = frozenset(
    {"none", "optional", "required"}
)
_UPLOAD_SESSION_RECORD_TYPE = "upload_session"
_UPLOAD_SESSION_UPLOAD_LOOKUP_RECORD_TYPE = "upload_session_upload_lookup"
_TYPE_SERIALIZER = TypeSerializer()


class UploadStrategy(StrEnum):
    """Upload strategy options returned by initiate endpoint."""

    SINGLE = "single"
    MULTIPART = "multipart"


class UploadSessionStatus(StrEnum):
    """Lifecycle status for a persisted upload session."""

    INITIATED = "initiated"
    ACTIVE = "active"
    COMPLETED = "completed"
    ABORTED = "aborted"


@dataclass(slots=True, frozen=True, kw_only=True)
class UploadSessionRecord:
    """Persisted upload session metadata."""

    session_id: str
    upload_id: str | None
    scope_id: str
    key: str
    filename: str
    size_bytes: int
    content_type: str | None
    strategy: UploadStrategy
    part_size_bytes: int | None
    policy_id: str
    policy_version: str
    max_concurrency_hint: int
    sign_batch_size_hint: int
    accelerate_enabled: bool
    checksum_algorithm: str | None
    checksum_mode: str
    sign_requests_count: int
    sign_requests_limit: int | None
    resumable_until: datetime
    resumable_until_epoch: int
    status: UploadSessionStatus
    request_id: str | None
    created_at: datetime
    last_activity_at: datetime


class UploadSessionRepository(Protocol):
    """Persist and retrieve upload session records."""

    async def create(self, record: UploadSessionRecord) -> None:
        """Store a new upload session."""

    async def get_for_upload_id(
        self,
        *,
        upload_id: str,
    ) -> UploadSessionRecord | None:
        """Return one session using the authoritative upload-id lookup path."""

    async def list_expired_multipart(
        self,
        *,
        now_epoch: int,
        limit: int,
    ) -> list[UploadSessionRecord]:
        """Return expired multipart sessions that still need cleanup."""
        ...

    async def update(self, record: UploadSessionRecord) -> None:
        """Replace an existing session record."""

    async def healthcheck(self) -> bool:
        """Return readiness of the backing store."""
        ...


@dataclass(slots=True)
class MemoryUploadSessionRepository:
    """In-memory upload session repository used for tests and fallback."""

    _records_by_session_id: dict[str, UploadSessionRecord]
    _records_by_upload_id: dict[str, UploadSessionRecord]
    _lock: asyncio.Lock = field(init=False, repr=False)

    def __init__(self) -> None:
        """Initialize empty in-memory upload session state."""
        self._records_by_session_id = {}
        self._records_by_upload_id = {}
        self._lock = asyncio.Lock()

    async def create(self, record: UploadSessionRecord) -> None:
        """Store one upload session record in memory."""
        async with self._lock:
            self._records_by_session_id[record.session_id] = record
            if record.upload_id is not None:
                self._records_by_upload_id[record.upload_id] = record

    async def get_for_upload_id(
        self,
        *,
        upload_id: str,
    ) -> UploadSessionRecord | None:
        """Return one in-memory session for the provided upload id."""
        async with self._lock:
            record = self._records_by_upload_id.get(upload_id)
            if record is None:
                return None
            if _is_expired(record):
                self._records_by_session_id.pop(record.session_id, None)
                self._records_by_upload_id.pop(upload_id, None)
                return None
            return record

    async def update(self, record: UploadSessionRecord) -> None:
        """Replace one in-memory upload session record."""
        async with self._lock:
            self._records_by_session_id[record.session_id] = record
            if record.upload_id is not None:
                self._records_by_upload_id[record.upload_id] = record

    async def list_expired_multipart(
        self,
        *,
        now_epoch: int,
        limit: int,
    ) -> list[UploadSessionRecord]:
        """Return expired multipart sessions that still need cleanup."""
        async with self._lock:
            expired = [
                record
                for record in self._records_by_session_id.values()
                if record.upload_id is not None
                and record.strategy == UploadStrategy.MULTIPART
                and record.status
                in {
                    UploadSessionStatus.INITIATED,
                    UploadSessionStatus.ACTIVE,
                }
                and record.resumable_until_epoch <= now_epoch
            ]
        expired.sort(key=lambda record: record.last_activity_at)
        return expired[:limit]

    async def healthcheck(self) -> bool:
        """Report readiness for the in-memory session repository."""
        return True


class DynamoTable(Protocol):
    """Subset of DynamoDB table operations used by upload sessions."""

    async def put_item(self, **kwargs: object) -> Mapping[str, object]:
        """Create or replace an item."""
        ...

    async def get_item(self, **kwargs: object) -> Mapping[str, object]:
        """Read a single item by key."""
        ...

    async def scan(self, **kwargs: object) -> Mapping[str, object]:
        """Scan items with optional filters."""
        ...


class DynamoResource(Protocol):
    """Subset of DynamoDB resource operations used by upload sessions."""

    def Table(self, table_name: str) -> DynamoTable | Any:
        """Return table object or awaitable table object."""


def _as_dynamo_table(table: object) -> DynamoTable:
    """Validate and cast a DynamoDB table-like object."""
    invalid_methods: list[str] = []
    for method_name in ("put_item", "get_item", "scan"):
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
class DynamoUploadSessionRepository:
    """DynamoDB-backed upload session repository."""

    table_name: str
    dynamodb_resource: DynamoResource
    _table: DynamoTable | None = field(init=False, repr=False, default=None)
    _table_lock: asyncio.Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the lazy DynamoDB table resolver."""
        self._table_lock = asyncio.Lock()

    async def create(self, record: UploadSessionRecord) -> None:
        """Persist one upload session record to DynamoDB."""
        table = await self._resolve_table()
        await _transact_write_put_items(
            table_name=self.table_name,
            table=table,
            items=_record_to_items(record),
        )

    async def get_for_upload_id(
        self,
        *,
        upload_id: str,
    ) -> UploadSessionRecord | None:
        """Return one persisted session by authoritative upload-id key."""
        table = await self._resolve_table()
        # Multipart continuation reads are authoritative on the base-table
        # alias row keyed by upload_id, so the read can stay strongly
        # consistent without any GSI dependency.
        direct = await table.get_item(
            Key={"session_id": upload_id},
            ConsistentRead=True,
        )
        direct_item = cast(dict[str, Any] | None, direct.get("Item"))
        if direct_item is None or not _is_upload_lookup_item(direct_item):
            return None
        record = _item_to_record(direct_item)
        if _is_expired(record):
            return None
        return record

    async def update(self, record: UploadSessionRecord) -> None:
        """Replace one upload session record in DynamoDB."""
        table = await self._resolve_table()
        await _transact_write_put_items(
            table_name=self.table_name,
            table=table,
            items=_record_to_items(record),
        )

    async def list_expired_multipart(
        self,
        *,
        now_epoch: int,
        limit: int,
    ) -> list[UploadSessionRecord]:
        """Return expired multipart sessions that still need cleanup."""
        table = await self._resolve_table()
        records: list[UploadSessionRecord] = []
        exclusive_start_key: dict[str, Any] | None = None
        while len(records) < limit:
            scan_kwargs: dict[str, object] = {
                "FilterExpression": (
                    "(attribute_not_exists(#record_type) "
                    "OR #record_type = :session_record) "
                    "AND #strategy = :multipart "
                    "AND #status IN (:initiated, :active) "
                    "AND #resumable_until_epoch <= :now_epoch"
                ),
                "ExpressionAttributeNames": {
                    "#record_type": "record_type",
                    "#strategy": "strategy",
                    "#status": "status",
                    "#resumable_until_epoch": "resumable_until_epoch",
                },
                "ExpressionAttributeValues": {
                    ":session_record": _UPLOAD_SESSION_RECORD_TYPE,
                    ":multipart": UploadStrategy.MULTIPART.value,
                    ":initiated": UploadSessionStatus.INITIATED.value,
                    ":active": UploadSessionStatus.ACTIVE.value,
                    ":now_epoch": now_epoch,
                },
                "Limit": limit,
            }
            if exclusive_start_key is not None:
                scan_kwargs["ExclusiveStartKey"] = exclusive_start_key
            response = await table.scan(**scan_kwargs)
            items = cast(list[dict[str, Any]], response.get("Items", []))
            records.extend(_item_to_record(item) for item in items)
            exclusive_start_key = cast(
                dict[str, Any] | None,
                response.get("LastEvaluatedKey"),
            )
            if exclusive_start_key is None:
                break
        records.sort(key=lambda record: record.last_activity_at)
        return records[:limit]

    async def healthcheck(self) -> bool:
        """Report readiness for the DynamoDB session repository."""
        try:
            table = await self._resolve_table()
            await table.get_item(Key={"session_id": "__health_check__"})
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


def _record_to_item(
    record: UploadSessionRecord,
    *,
    record_type: str,
    session_lookup_key: str,
    include_upload_id: bool,
) -> dict[str, object]:
    item: dict[str, object] = {
        "session_id": session_lookup_key,
        "canonical_session_id": record.session_id,
        "scope_id": record.scope_id,
        "key": record.key,
        "filename": record.filename,
        "size_bytes": record.size_bytes,
        "content_type": record.content_type,
        "strategy": record.strategy.value,
        "part_size_bytes": record.part_size_bytes,
        "policy_id": record.policy_id,
        "policy_version": record.policy_version,
        "max_concurrency_hint": record.max_concurrency_hint,
        "sign_batch_size_hint": record.sign_batch_size_hint,
        "accelerate_enabled": record.accelerate_enabled,
        "checksum_algorithm": record.checksum_algorithm,
        "checksum_mode": record.checksum_mode,
        "sign_requests_count": record.sign_requests_count,
        "sign_requests_limit": record.sign_requests_limit,
        "resumable_until": record.resumable_until.isoformat(),
        "resumable_until_epoch": record.resumable_until_epoch,
        "status": record.status.value,
        "record_type": record_type,
        "request_id": record.request_id,
        "created_at": record.created_at.isoformat(),
        "last_activity_at": record.last_activity_at.isoformat(),
    }
    if include_upload_id and record.upload_id is not None:
        item["upload_id"] = record.upload_id
    return item


def _record_to_items(record: UploadSessionRecord) -> list[dict[str, object]]:
    items = [
        _record_to_item(
            record,
            record_type=_UPLOAD_SESSION_RECORD_TYPE,
            session_lookup_key=record.session_id,
            include_upload_id=True,
        )
    ]
    if record.upload_id is not None:
        items.append(
            _record_to_item(
                record,
                record_type=_UPLOAD_SESSION_UPLOAD_LOOKUP_RECORD_TYPE,
                session_lookup_key=record.upload_id,
                include_upload_id=False,
            )
        )
    return items


def _dynamo_transact_write_client(table: object) -> object | None:
    """Return the DynamoDB client exposing ``transact_write_items``."""
    meta = getattr(table, "meta", None)
    client = getattr(meta, "client", None) if meta is not None else None
    if client is None:
        return None
    if not callable(getattr(client, "transact_write_items", None)):
        return None
    return cast(object, client)


async def _transact_write_put_items(
    *,
    table_name: str,
    table: DynamoTable,
    items: list[dict[str, object]],
) -> None:
    """Write all rows for one upload session as a single transaction."""
    client = _dynamo_transact_write_client(table)
    if client is None:
        for item in items:
            await table.put_item(Item=item)
        return
    transact_write_items = cast(
        Any,
        client,
    ).transact_write_items
    await transact_write_items(
        TransactItems=[
            {
                "Put": {
                    "TableName": table_name,
                    "Item": _serialize_item(item),
                }
            }
            for item in items
        ]
    )


def _serialize_item(item: dict[str, object]) -> dict[str, object]:
    return {
        key: cast(object, _TYPE_SERIALIZER.serialize(value))
        for key, value in item.items()
    }


def _parse_checksum_mode(item: dict[str, Any]) -> str:
    raw = item.get("checksum_mode")
    if raw is None:
        return "none"
    if not isinstance(raw, str):
        raise TypeError(
            "upload session checksum_mode must be a string when present"
        )
    if raw not in _ALLOWED_UPLOAD_SESSION_CHECKSUM_MODES:
        raise ValueError(
            "upload session checksum_mode must be one of "
            f"{sorted(_ALLOWED_UPLOAD_SESSION_CHECKSUM_MODES)}"
        )
    return raw


def _item_to_record(item: dict[str, Any]) -> UploadSessionRecord:
    def _as_str(value: object) -> str | None:
        return value if isinstance(value, str) else None

    def _as_int(value: object) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int):
            return int(value)
        if isinstance(value, Decimal):
            return int(value)
        return None

    def _as_bool(value: object) -> bool:
        return bool(value) if isinstance(value, bool) else False

    def _parse_datetime(value: object) -> datetime:
        if isinstance(value, datetime):
            return (
                value if value.tzinfo is not None else value.replace(tzinfo=UTC)
            )
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            return (
                parsed
                if parsed.tzinfo is not None
                else parsed.replace(tzinfo=UTC)
            )
        raise TypeError("upload session timestamps must be datetime strings")

    record_type = _record_type(item)
    upload_id = _as_str(item.get("upload_id"))
    if (
        upload_id is None
        and record_type == _UPLOAD_SESSION_UPLOAD_LOOKUP_RECORD_TYPE
    ):
        upload_id = _as_str(item.get("session_id"))
    session_id = _as_str(item.get("canonical_session_id"))
    if session_id is None:
        session_id = _as_str(item.get("session_id"))
    if session_id is None:
        raise TypeError("upload session session_id must be a string")
    strategy = UploadStrategy(str(item["strategy"]))
    status = UploadSessionStatus(str(item["status"]))
    checksum_algorithm = _as_str(item.get("checksum_algorithm"))
    checksum_mode = _parse_checksum_mode(item)
    return UploadSessionRecord(
        session_id=session_id,
        upload_id=upload_id,
        scope_id=str(item["scope_id"]),
        key=str(item["key"]),
        filename=str(item["filename"]),
        size_bytes=int(item["size_bytes"]),
        content_type=_as_str(item.get("content_type")),
        strategy=strategy,
        part_size_bytes=_as_int(item.get("part_size_bytes")),
        policy_id=str(item["policy_id"]),
        policy_version=str(item["policy_version"]),
        max_concurrency_hint=int(item["max_concurrency_hint"]),
        sign_batch_size_hint=int(item["sign_batch_size_hint"]),
        accelerate_enabled=_as_bool(item.get("accelerate_enabled")),
        checksum_algorithm=checksum_algorithm,
        checksum_mode=checksum_mode,
        sign_requests_count=int(item.get("sign_requests_count", 0)),
        sign_requests_limit=_as_int(item.get("sign_requests_limit")),
        resumable_until=_parse_datetime(item["resumable_until"]),
        resumable_until_epoch=int(item["resumable_until_epoch"]),
        status=status,
        request_id=_as_str(item.get("request_id")),
        created_at=_parse_datetime(item["created_at"]),
        last_activity_at=_parse_datetime(item["last_activity_at"]),
    )


def _record_type(item: Mapping[str, Any]) -> str | None:
    raw = item.get("record_type")
    return raw if isinstance(raw, str) else None


def _is_upload_lookup_item(item: Mapping[str, Any]) -> bool:
    return _record_type(item) == _UPLOAD_SESSION_UPLOAD_LOOKUP_RECORD_TYPE


def new_upload_session_id() -> str:
    """Return a stable new session identifier."""
    return uuid4().hex


def _is_expired(record: UploadSessionRecord) -> bool:
    return record.resumable_until_epoch <= int(time.time())


def build_upload_session_repository(
    *,
    table_name: str | None,
    dynamodb_resource: DynamoResource | None,
    enabled: bool,
) -> UploadSessionRepository:
    """Create the configured upload-session repository."""
    resolved_table_name = (table_name or "").strip()
    if not enabled:
        return MemoryUploadSessionRepository()
    if not resolved_table_name:
        raise ValueError(
            "FILE_TRANSFER_UPLOAD_SESSIONS_TABLE must be configured "
            "when FILE_TRANSFER_ENABLED=true"
        )
    if dynamodb_resource is None:
        raise ValueError(
            "dynamodb_resource must be provided when file transfer "
            "sessions are enabled"
        )
    return DynamoUploadSessionRepository(
        table_name=resolved_table_name,
        dynamodb_resource=dynamodb_resource,
    )
