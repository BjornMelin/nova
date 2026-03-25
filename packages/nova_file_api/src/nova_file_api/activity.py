"""Activity tracking and rollup backends."""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, TypeAlias

from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.models import Principal

logger = logging.getLogger(__name__)

DynamoAttributeValue: TypeAlias = dict[str, str]
DynamoItem: TypeAlias = dict[str, DynamoAttributeValue]
DynamoKey: TypeAlias = DynamoItem


class ActivityStore(Protocol):
    """Interface for activity rollup storage."""

    async def record(
        self,
        *,
        principal: Principal,
        event_type: str,
        details: str | None = None,
    ) -> None:
        """Record one activity event for a principal.

        Args:
            principal: Authenticated principal that triggered the event.
            event_type: Event name used for daily counters.
            details: Optional diagnostic context for structured logs.

        Returns:
            None

        Note:
            Errors from the backing store are caught and logged; this method
            does not raise ClientError or BotoCoreError.
        """

    async def summary(self) -> dict[str, int]:
        """Return aggregate summary counters.

        Returns:
            Daily counters for total events, active users, and event-type
            cardinality.
        """

    async def healthcheck(self) -> bool:
        """Return readiness of the activity store backend.

        Returns:
            True when the backing store can be queried for health.
        """


class DynamoDbClientProtocol(Protocol):
    """Subset of DynamoDB client methods used by rollup storage."""

    async def update_item(
        self,
        *,
        TableName: str,
        Key: DynamoKey,
        UpdateExpression: str,
        ExpressionAttributeNames: dict[str, str],
        ExpressionAttributeValues: DynamoItem,
    ) -> object:
        """Update a DynamoDB item."""

    async def put_item(
        self,
        *,
        TableName: str,
        Item: DynamoItem,
        ConditionExpression: str,
    ) -> object:
        """Put a DynamoDB item."""

    async def get_item(
        self,
        *,
        TableName: str,
        Key: DynamoKey,
    ) -> dict[str, DynamoItem]:
        """Get a DynamoDB item."""


@dataclass(slots=True)
class MemoryActivityStore:
    """In-memory activity aggregation."""

    _events_per_day: dict[str, dict[str, int]]
    _subjects_per_day: dict[str, set[str]]
    _lock: threading.Lock

    def __init__(self) -> None:
        """Initialize in-memory counters and subject sets."""
        self._events_per_day = defaultdict(lambda: defaultdict(int))
        self._subjects_per_day = defaultdict(set)
        self._lock = threading.Lock()

    async def record(
        self,
        *,
        principal: Principal,
        event_type: str,
        details: str | None = None,
    ) -> None:
        """Record one event for the principal and current day.

        Args:
            principal: Authenticated principal associated with the event.
            event_type: Event name used for counters.
            details: Optional diagnostic details emitted to logs.

        Returns:
            None
        """
        day = _day_key()
        if details is not None:
            logger.info(
                "memory activity record received details",
                extra=_record_log_context(
                    principal=principal,
                    event_type=event_type,
                    day=day,
                    table=None,
                    details=details,
                ),
            )
        with self._lock:
            self._events_per_day[day][event_type] += 1
            self._subjects_per_day[day].add(principal.subject)

    async def summary(self) -> dict[str, int]:
        """Return aggregate counters for dashboard display.

        Returns:
            Daily counters for total events, active users, and distinct event
            types.
        """
        day = _day_key()
        with self._lock:
            day_events = dict(self._events_per_day.get(day, {}))
            active_users_today = len(self._subjects_per_day.get(day, set()))
        total_events = sum(day_events.values())
        return {
            "events_total": total_events,
            "active_users_today": active_users_today,
            "distinct_event_types": len(day_events),
        }

    async def healthcheck(self) -> bool:
        """Report readiness for the in-memory activity store.

        Returns:
            True because in-memory rollups have no external dependency.
        """
        return True


class DynamoActivityStore:
    """DynamoDB-backed daily rollups for activity dashboards."""

    def __init__(
        self,
        *,
        table_name: str,
        ddb_client: DynamoDbClientProtocol,
    ) -> None:
        """Create a rollup store bound to the configured table.

        Args:
            table_name: DynamoDB table name for activity rollups.
            ddb_client: Injected async DynamoDB client.
        """
        self._table_name = table_name
        self._ddb: DynamoDbClientProtocol = ddb_client

    async def record(
        self,
        *,
        principal: Principal,
        event_type: str,
        details: str | None = None,
    ) -> None:
        """Update activity counters for one event.

        Args:
            principal: Authenticated caller principal.
            event_type: Event name for per-type counters.
            details: Optional diagnostic context from failure paths.

        Returns:
            None

        Note:
            Errors from DynamoDB are caught and logged; this method does not
            raise ClientError or BotoCoreError.
        """
        day = _day_key()
        context = _record_log_context(
            principal=principal,
            event_type=event_type,
            day=day,
            table=self._table_name,
            details=details,
        )
        summary_key = {"pk": {"S": f"ROLLUP#{day}"}, "sk": {"S": "SUMMARY"}}
        user_marker_key = {
            "pk": {"S": f"USERDAY#{day}"},
            "sk": {"S": principal.subject},
        }
        event_rollup_key = {
            "pk": {"S": f"ROLLUP#{day}"},
            "sk": {"S": f"EVENT#{event_type}"},
        }
        event_type_marker_key = {
            "pk": {"S": f"EVENTTYPEDAY#{day}"},
            "sk": {"S": event_type},
        }
        try:
            await self._increment_counter(
                key=event_rollup_key, counter_name="event_count"
            )
            await self._increment_counter(
                key=summary_key, counter_name="events_total"
            )
        except (ClientError, BotoCoreError) as exc:
            logger.warning(
                "activity rollup counter updates failed",
                extra={**context, "error_type": exc.__class__.__name__},
                exc_info=exc,
            )
            return

        try:
            user_was_new = await self._write_marker_if_absent(
                key=user_marker_key
            )
        except (ClientError, BotoCoreError) as exc:
            logger.warning(
                "activity user marker write failed; "
                "skipping user marker accounting",
                extra={**context, "error_type": exc.__class__.__name__},
                exc_info=exc,
            )
            user_was_new = False
        if user_was_new:
            try:
                await self._increment_counter(
                    key=summary_key, counter_name="active_users_today"
                )
            except (ClientError, BotoCoreError) as exc:
                logger.warning(
                    "activity distinct active user increment failed",
                    extra={**context, "error_type": exc.__class__.__name__},
                    exc_info=exc,
                )

        try:
            event_type_was_new = await self._write_marker_if_absent(
                key=event_type_marker_key
            )
        except (ClientError, BotoCoreError) as exc:
            logger.warning(
                "activity event-type marker write failed; "
                "skipping event-type accounting",
                extra={**context, "error_type": exc.__class__.__name__},
                exc_info=exc,
            )
            event_type_was_new = False
        if event_type_was_new:
            try:
                await self._increment_counter(
                    key=summary_key, counter_name="distinct_event_types"
                )
            except (ClientError, BotoCoreError) as exc:
                logger.warning(
                    "activity distinct event-type increment failed",
                    extra={**context, "error_type": exc.__class__.__name__},
                    exc_info=exc,
                )

    async def summary(self) -> dict[str, int]:
        """Read current-day aggregate counters from DynamoDB.

        Returns:
            Daily counters for total events, active users, and distinct event
            types.
        """
        day = _day_key()
        try:
            response = await self._ddb.get_item(
                TableName=self._table_name,
                Key={"pk": {"S": f"ROLLUP#{day}"}, "sk": {"S": "SUMMARY"}},
            )
        except (ClientError, BotoCoreError):
            return {
                "events_total": 0,
                "active_users_today": 0,
                "distinct_event_types": 0,
            }
        item = response.get("Item")
        if item is None:
            return {
                "events_total": 0,
                "active_users_today": 0,
                "distinct_event_types": 0,
            }
        return {
            "events_total": int(item.get("events_total", {"N": "0"})["N"]),
            "active_users_today": int(
                item.get("active_users_today", {"N": "0"})["N"]
            ),
            "distinct_event_types": int(
                item.get("distinct_event_types", {"N": "0"})["N"]
            ),
        }

    async def healthcheck(self) -> bool:
        """Return True when the configured rollup table can be queried.

        Returns:
            True when the health probe query succeeds, otherwise False.
        """
        try:
            await self._ddb.get_item(
                TableName=self._table_name,
                Key={"pk": {"S": "ROLLUP#health"}, "sk": {"S": "SUMMARY"}},
            )
        except (ClientError, BotoCoreError):
            return False
        return True

    async def _increment_counter(
        self,
        *,
        key: dict[str, dict[str, str]],
        counter_name: str,
    ) -> None:
        """Increment one numeric counter on the target item."""
        await self._ddb.update_item(
            TableName=self._table_name,
            Key=key,
            UpdateExpression=(
                "SET #updated_at = :updated_at ADD #counter :increment"
            ),
            ExpressionAttributeNames={
                "#counter": counter_name,
                "#updated_at": "updated_at",
            },
            ExpressionAttributeValues={
                ":increment": {"N": "1"},
                ":updated_at": {"S": _iso_now()},
            },
        )

    async def _write_marker_if_absent(
        self,
        *,
        key: dict[str, dict[str, str]],
    ) -> bool:
        """Write a marker item only if absent, returning True on creation."""
        try:
            await self._ddb.put_item(
                TableName=self._table_name,
                Item={
                    **key,
                    "expires_at": {"N": _ttl_for_days(2)},
                    "created_at": {"S": _iso_now()},
                },
                ConditionExpression="attribute_not_exists(pk)",
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code == "ConditionalCheckFailedException":
                return False
            raise
        else:
            return True


def _record_log_context(
    *,
    principal: Principal,
    event_type: str,
    day: str,
    table: str | None,
    details: str | None,
) -> dict[str, str | int | None]:
    context: dict[str, str | int | None] = {
        "event_type": event_type,
        "day": day,
        "principal_fingerprint": _principal_fingerprint(principal=principal),
    }
    if table is not None:
        context["table"] = table
    sanitized_details = _sanitize_details(details)
    if sanitized_details is not None:
        context["details"] = sanitized_details
    return context


def _sanitize_details(details: str | None) -> str | None:
    if details is None:
        return None
    redacted = re.sub(
        r"\b(?:[A-Za-z0-9_-]{16,}\.){2}[A-Za-z0-9_-]{16,}\b",
        "[REDACTED_TOKEN]",
        details,
    )
    redacted = re.sub(
        r"(?i)(authorization\s*[:=]\s*)([^\r\n,;]+)",
        r"\1[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)\bbearer\s+[^\r\n,;]+",
        "[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)(token\s*[:=]\s*)([^\r\n,;]+)",
        r"\1[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)(secret\s*[:=]\s*)([^\r\n,;]+)",
        r"\1[REDACTED]",
        redacted,
    )
    if len(redacted) > 256:
        return f"{redacted[:128]}...truncated"
    return redacted


def _principal_fingerprint(*, principal: Principal) -> str:
    digest = hashlib.sha256(principal.subject.encode("utf-8")).hexdigest()
    return digest[:16]


def _day_key() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%d")


def _iso_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _ttl_for_days(days: int) -> str:
    ttl = int(datetime.now(tz=UTC).timestamp()) + (days * 24 * 60 * 60)
    return str(ttl)
