"""Quota accounting for transfer control-plane activity."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast

from botocore.exceptions import BotoCoreError, ClientError


@dataclass(slots=True)
class TransferQuotaExceeded(RuntimeError):
    """Raised when a quota counter cannot reserve additional capacity."""

    reason: str
    details: dict[str, int]

    def __post_init__(self) -> None:
        """Populate the base exception message from the quota reason."""
        RuntimeError.__init__(self, self.reason)


class TransferUsageWindowRepository(Protocol):
    """Persist quota counters for transfer activity."""

    async def reserve_upload(
        self,
        *,
        scope_id: str,
        window_started_at: datetime,
        size_bytes: int,
        multipart: bool,
        active_multipart_limit: int | None,
        daily_ingress_budget_bytes: int | None,
    ) -> None:
        """Reserve quota for one initiated upload."""

    async def release_upload(
        self,
        *,
        scope_id: str,
        window_started_at: datetime,
        size_bytes: int,
        multipart: bool,
        completed: bool,
    ) -> None:
        """Release quota after a failed or terminal upload."""

    async def record_sign_request(
        self,
        *,
        scope_id: str,
        window_started_at: datetime,
        hourly_sign_request_limit: int | None,
    ) -> None:
        """Record one sign-parts request."""

    async def healthcheck(self) -> bool:
        """Return readiness of the quota backend."""


@dataclass(slots=True)
class MemoryTransferUsageRepository:
    """In-memory transfer usage counters used for tests and fallback."""

    _counters: dict[tuple[str, str], dict[str, int]]
    _lock: asyncio.Lock = field(init=False, repr=False)

    def __init__(self) -> None:
        """Initialize empty in-memory counters."""
        self._counters = {}
        self._lock = asyncio.Lock()

    async def reserve_upload(
        self,
        *,
        scope_id: str,
        window_started_at: datetime,
        size_bytes: int,
        multipart: bool,
        active_multipart_limit: int | None,
        daily_ingress_budget_bytes: int | None,
    ) -> None:
        """Reserve upload quota for one initiate request."""
        async with self._lock:
            if multipart and active_multipart_limit is not None:
                active = self._counter(
                    scope_id=scope_id,
                    window_key="active",
                ).get("active_multipart_uploads", 0)
                if active >= active_multipart_limit:
                    raise TransferQuotaExceeded(
                        reason="active_multipart_limit",
                        details={"limit": active_multipart_limit},
                    )
            daily_counters = self._counter(
                scope_id=scope_id,
                window_key=_daily_window_key(window_started_at),
            )
            if daily_ingress_budget_bytes is not None:
                current_bytes = daily_counters.get("bytes_initiated", 0)
                if current_bytes + size_bytes > daily_ingress_budget_bytes:
                    raise TransferQuotaExceeded(
                        reason="daily_ingress_budget_bytes",
                        details={"limit": daily_ingress_budget_bytes},
                    )
            daily_counters["bytes_initiated"] = (
                daily_counters.get("bytes_initiated", 0) + size_bytes
            )
            if multipart:
                active_counters = self._counter(
                    scope_id=scope_id,
                    window_key="active",
                )
                active_counters["active_multipart_uploads"] = (
                    active_counters.get("active_multipart_uploads", 0) + 1
                )

    async def release_upload(
        self,
        *,
        scope_id: str,
        window_started_at: datetime,
        size_bytes: int,
        multipart: bool,
        completed: bool,
    ) -> None:
        """Release upload quota after a rollback or terminal transition."""
        async with self._lock:
            daily_counters = self._counter(
                scope_id=scope_id,
                window_key=_daily_window_key(window_started_at),
            )
            if not completed:
                current = daily_counters.get("bytes_initiated", 0)
                daily_counters["bytes_initiated"] = max(0, current - size_bytes)
            if multipart:
                active_counters = self._counter(
                    scope_id=scope_id,
                    window_key="active",
                )
                active = active_counters.get("active_multipart_uploads", 0)
                active_counters["active_multipart_uploads"] = max(0, active - 1)

    async def record_sign_request(
        self,
        *,
        scope_id: str,
        window_started_at: datetime,
        hourly_sign_request_limit: int | None,
    ) -> None:
        """Record one sign-parts request in the active hourly window."""
        async with self._lock:
            counters = self._counter(
                scope_id=scope_id,
                window_key=_hourly_window_key(window_started_at),
            )
            current = counters.get("sign_requests", 0)
            if (
                hourly_sign_request_limit is not None
                and current >= hourly_sign_request_limit
            ):
                raise TransferQuotaExceeded(
                    reason="hourly_sign_request_limit",
                    details={"limit": hourly_sign_request_limit},
                )
            counters["sign_requests"] = current + 1

    async def healthcheck(self) -> bool:
        """Report readiness for the in-memory repository."""
        return True

    def _counter(self, *, scope_id: str, window_key: str) -> dict[str, int]:
        return self._counters.setdefault((scope_id, window_key), {})


class DynamoTable(Protocol):
    """Subset of DynamoDB table operations used by usage counters."""

    async def get_item(self, **kwargs: object) -> Mapping[str, object]:
        """Read one item by key."""

    async def update_item(self, **kwargs: object) -> Mapping[str, object]:
        """Update one item by key."""


class DynamoResource(Protocol):
    """Subset of DynamoDB resource operations used by usage counters."""

    def Table(self, table_name: str) -> DynamoTable | Any:
        """Return table object or awaitable table object."""


def _as_dynamo_table(table: object) -> DynamoTable:
    invalid_methods: list[str] = []
    for method_name in ("get_item", "update_item"):
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
class DynamoTransferUsageRepository:
    """DynamoDB-backed transfer usage counters."""

    table_name: str
    dynamodb_resource: DynamoResource
    _table: DynamoTable | None = field(init=False, repr=False, default=None)
    _table_lock: asyncio.Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the lazy DynamoDB table resolver."""
        self._table_lock = asyncio.Lock()

    async def reserve_upload(
        self,
        *,
        scope_id: str,
        window_started_at: datetime,
        size_bytes: int,
        multipart: bool,
        active_multipart_limit: int | None,
        daily_ingress_budget_bytes: int | None,
    ) -> None:
        """Reserve upload quota for one initiate request in DynamoDB."""
        if daily_ingress_budget_bytes is not None:
            await self._reserve_daily_ingress_bytes(
                scope_id=scope_id,
                size_bytes=size_bytes,
                limit=daily_ingress_budget_bytes,
                now=window_started_at,
            )
        try:
            if multipart and active_multipart_limit is not None:
                await self._reserve_active_multipart_slot(
                    scope_id=scope_id,
                    limit=active_multipart_limit,
                )
        except asyncio.CancelledError:
            if daily_ingress_budget_bytes is not None:
                await self._release_daily_ingress_bytes(
                    scope_id=scope_id,
                    size_bytes=size_bytes,
                    now=window_started_at,
                )
            raise
        except Exception:
            if daily_ingress_budget_bytes is not None:
                await self._release_daily_ingress_bytes(
                    scope_id=scope_id,
                    size_bytes=size_bytes,
                    now=window_started_at,
                )
            raise

    async def release_upload(
        self,
        *,
        scope_id: str,
        window_started_at: datetime,
        size_bytes: int,
        multipart: bool,
        completed: bool,
    ) -> None:
        """Release upload quota after rollback or terminal completion."""
        if not completed:
            await self._release_daily_ingress_bytes(
                scope_id=scope_id,
                size_bytes=size_bytes,
                now=window_started_at,
            )
        if multipart:
            await self._release_active_multipart_slot(scope_id=scope_id)

    async def record_sign_request(
        self,
        *,
        scope_id: str,
        window_started_at: datetime,
        hourly_sign_request_limit: int | None,
    ) -> None:
        """Record one sign-parts request in DynamoDB."""
        table = await self._resolve_table()
        window_key = _hourly_window_key(window_started_at)
        expires_at = _hourly_window_expiry_epoch(window_started_at)
        try:
            await table.update_item(
                Key=_usage_key(scope_id=scope_id, window_key=window_key),
                UpdateExpression=(
                    "ADD sign_requests :inc "
                    "SET expires_at = :expires_at, updated_at = :updated_at"
                ),
                ConditionExpression=(
                    "attribute_not_exists(sign_requests) "
                    "OR :limit = :no_limit "
                    "OR sign_requests < :limit"
                ),
                ExpressionAttributeValues={
                    ":inc": 1,
                    ":limit": hourly_sign_request_limit or -1,
                    ":no_limit": -1,
                    ":expires_at": expires_at,
                    ":updated_at": _iso_now(),
                },
            )
        except ClientError as exc:
            if _is_conditional_failure(exc):
                raise TransferQuotaExceeded(
                    reason="hourly_sign_request_limit",
                    details={"limit": hourly_sign_request_limit or 0},
                ) from exc
            raise

    async def healthcheck(self) -> bool:
        """Report readiness for the DynamoDB repository."""
        try:
            table = await self._resolve_table()
            await table.get_item(
                Key={"scope_id": "__health_check__", "window_key": "active"}
            )
        except (ClientError, BotoCoreError):
            return False
        return True

    async def _reserve_active_multipart_slot(
        self,
        *,
        scope_id: str,
        limit: int,
    ) -> None:
        table = await self._resolve_table()
        now = datetime.now(tz=UTC)
        try:
            await table.update_item(
                Key=_usage_key(scope_id=scope_id, window_key="active"),
                UpdateExpression=(
                    "ADD active_multipart_uploads :inc "
                    "SET expires_at = :expires_at, updated_at = :updated_at"
                ),
                ConditionExpression=(
                    "attribute_not_exists(active_multipart_uploads) "
                    "OR active_multipart_uploads < :limit"
                ),
                ExpressionAttributeValues={
                    ":inc": 1,
                    ":limit": limit,
                    ":expires_at": _active_window_expiry_epoch(now),
                    ":updated_at": _iso_now(now),
                },
            )
        except ClientError as exc:
            if _is_conditional_failure(exc):
                raise TransferQuotaExceeded(
                    reason="active_multipart_limit",
                    details={"limit": limit},
                ) from exc
            raise

    async def _release_active_multipart_slot(self, *, scope_id: str) -> None:
        table = await self._resolve_table()
        now = datetime.now(tz=UTC)
        try:
            await table.update_item(
                Key=_usage_key(scope_id=scope_id, window_key="active"),
                UpdateExpression=(
                    "ADD active_multipart_uploads :dec "
                    "SET expires_at = :expires_at, updated_at = :updated_at"
                ),
                ConditionExpression=(
                    "attribute_exists(active_multipart_uploads) "
                    "AND active_multipart_uploads > :zero"
                ),
                ExpressionAttributeValues={
                    ":dec": -1,
                    ":zero": 0,
                    ":expires_at": _active_window_expiry_epoch(now),
                    ":updated_at": _iso_now(now),
                },
            )
        except ClientError as exc:
            if not _is_conditional_failure(exc):
                raise

    async def _reserve_daily_ingress_bytes(
        self,
        *,
        scope_id: str,
        size_bytes: int,
        limit: int,
        now: datetime,
    ) -> None:
        table = await self._resolve_table()
        window_key = _daily_window_key(now)
        expires_at = _daily_window_expiry_epoch(now)
        if size_bytes > limit:
            raise TransferQuotaExceeded(
                reason="daily_ingress_budget_bytes",
                details={"limit": limit},
            )
        try:
            await table.update_item(
                Key=_usage_key(scope_id=scope_id, window_key=window_key),
                UpdateExpression=(
                    "ADD bytes_initiated :size_bytes "
                    "SET expires_at = :expires_at, updated_at = :updated_at"
                ),
                ConditionExpression=(
                    "attribute_not_exists(bytes_initiated) "
                    "OR bytes_initiated <= :remaining_bytes"
                ),
                ExpressionAttributeValues={
                    ":size_bytes": size_bytes,
                    ":remaining_bytes": limit - size_bytes,
                    ":expires_at": expires_at,
                    ":updated_at": _iso_now(now),
                },
            )
        except ClientError as exc:
            if _is_conditional_failure(exc):
                raise TransferQuotaExceeded(
                    reason="daily_ingress_budget_bytes",
                    details={"limit": limit},
                ) from exc
            raise

    async def _release_daily_ingress_bytes(
        self,
        *,
        scope_id: str,
        size_bytes: int,
        now: datetime,
    ) -> None:
        table = await self._resolve_table()
        window_key = _daily_window_key(now)
        try:
            await table.update_item(
                Key=_usage_key(scope_id=scope_id, window_key=window_key),
                UpdateExpression=(
                    "ADD bytes_initiated :size_bytes "
                    "SET updated_at = :updated_at"
                ),
                ConditionExpression=(
                    "attribute_exists(bytes_initiated) "
                    "AND bytes_initiated >= :minimum_bytes"
                ),
                ExpressionAttributeValues={
                    ":size_bytes": -size_bytes,
                    ":minimum_bytes": size_bytes,
                    ":updated_at": _iso_now(),
                },
            )
        except ClientError as exc:
            if not _is_conditional_failure(exc):
                raise

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


def build_transfer_usage_window_repository(
    *,
    table_name: str | None,
    dynamodb_resource: DynamoResource | None,
    enabled: bool,
) -> TransferUsageWindowRepository:
    """Create the configured transfer usage repository."""
    resolved_table_name = (table_name or "").strip()
    if not enabled:
        return MemoryTransferUsageRepository()
    if not resolved_table_name:
        raise ValueError(
            "FILE_TRANSFER_USAGE_TABLE must be configured when "
            "FILE_TRANSFER_ENABLED=true"
        )
    if dynamodb_resource is None:
        raise ValueError(
            "dynamodb_resource must be provided when transfer quota storage "
            "is enabled"
        )
    return DynamoTransferUsageRepository(
        table_name=resolved_table_name,
        dynamodb_resource=dynamodb_resource,
    )


def _daily_window_key(now: datetime) -> str:
    return f"daily#{_as_utc(now).strftime('%Y%m%d')}"


def _hourly_window_key(now: datetime) -> str:
    return f"hourly#{_as_utc(now).strftime('%Y%m%d%H')}"


def _daily_window_expiry_epoch(now: datetime) -> int:
    day_end = _as_utc(now).replace(hour=0, minute=0, second=0, microsecond=0)
    expiry = day_end + timedelta(days=2)
    return int(expiry.timestamp())


def _hourly_window_expiry_epoch(now: datetime) -> int:
    hour_end = _as_utc(now).replace(minute=0, second=0, microsecond=0)
    expiry = hour_end + timedelta(hours=2)
    return int(expiry.timestamp())


def _active_window_expiry_epoch(now: datetime) -> int:
    return int((_as_utc(now) + timedelta(days=7)).timestamp())


def _usage_key(*, scope_id: str, window_key: str) -> dict[str, str]:
    return {"scope_id": scope_id, "window_key": window_key}


def _as_utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now.astimezone(UTC)


def _iso_now(now: datetime | None = None) -> str:
    resolved = now if now is not None else datetime.now(tz=UTC)
    return _as_utc(resolved).isoformat()


def _is_conditional_failure(exc: ClientError) -> bool:
    return (
        str(exc.response.get("Error", {}).get("Code", ""))
        == "ConditionalCheckFailedException"
    )
