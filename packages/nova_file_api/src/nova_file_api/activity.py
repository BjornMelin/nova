"""Activity tracking and rollup backends."""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from _thread import LockType
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.models import Principal

logger = logging.getLogger(__name__)

type DynamoAttributeValue = dict[str, str]
type DynamoItem = dict[str, DynamoAttributeValue]
type DynamoKey = DynamoItem


class ActivityStore(Protocol):
    """Interface for activity rollup storage."""

    async def record(
        self,
        *,
        principal: Principal,
        event_type: str,
        details: str | None = None,
    ) -> None:
        """
        Record an activity event for the given principal and event type for today's rollup.
        
        Records a single occurrence of event_type associated with principal for the current UTC day. Optionally accepts a free-form details string which will be sanitized and truncated for logging and storage purposes.
        
        Parameters:
        	principal (Principal): The authenticated actor whose `subject` uniquely identifies the user.
        	event_type (str): A short identifier for the event being recorded (for example, "upload" or "login").
        	details (str | None): Optional additional information about the event; may be redacted or truncated before persisting.
        """

    async def summary(self) -> dict[str, int]:
        """
        Provide today's aggregate activity counters from the rollup store.
        
        Returns:
            dict[str, int]: A mapping with keys:
                - "events_total": total number of events recorded today,
                - "active_users_today": number of distinct principals observed today,
                - "distinct_event_types": number of distinct event types observed today.
            If the summary item is missing or an error occurs, all values will be 0.
        """

    async def healthcheck(self) -> bool:
        """
        Check whether the activity store backend is ready.
        
        Returns:
            `True` if the backend is reachable and operational, `False` otherwise.
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
        """
        Apply an UpdateItem expression to a DynamoDB item in the specified table.
        
        Parameters:
            TableName (str): Name of the DynamoDB table to update.
            Key (DynamoKey): Primary key of the item to update (DynamoDB attribute map).
            UpdateExpression (str): DynamoDB UpdateExpression describing the update.
            ExpressionAttributeNames (dict[str, str]): Mapping of expression attribute name placeholders (e.g., "#name") to actual attribute names.
            ExpressionAttributeValues (DynamoItem): Mapping of expression attribute value placeholders (e.g., ":val") to DynamoDB attribute value maps.
        
        Returns:
            object: The raw response object returned by the DynamoDB client for the UpdateItem call.
        """

    async def put_item(
        self,
        *,
        TableName: str,
        Item: DynamoItem,
        ConditionExpression: str,
    ) -> object:
        """
        Insert an item into the specified DynamoDB table when the provided condition is satisfied.
        
        Parameters:
            TableName (str): Name of the DynamoDB table to write to.
            Item (DynamoItem): Attribute map representing the item to put.
            ConditionExpression (str): DynamoDB condition expression that must evaluate to true for the put to succeed.
        
        Returns:
            object: The raw response returned by the DynamoDB client operation.
        """

    async def get_item(
        self,
        *,
        TableName: str,
        Key: DynamoKey,
    ) -> dict[str, DynamoItem]:
        """
        Retrieve an item from a DynamoDB table by primary key.
        
        Parameters:
            TableName (str): Name of the DynamoDB table to query.
            Key (DynamoKey): Primary key of the item to retrieve (attribute-name to DynamoDB attribute value map).
        
        Returns:
            dict[str, DynamoItem]: The raw DynamoDB response dictionary. If an item is found it appears under the 'Item' key as a mapping of attribute names to DynamoDB attribute values; otherwise the response will not contain 'Item' (commonly an empty dict).
        """


@dataclass(slots=True)
class MemoryActivityStore:
    """In-memory activity aggregation."""

    _events_per_day: dict[str, dict[str, int]]
    _subjects_per_day: dict[str, set[str]]
    _lock: LockType

    def __init__(self) -> None:
        """
        Initialize the store's in-memory counters, subject sets, and synchronization lock.
        
        Creates the following attributes:
        - _events_per_day: mapping from day string to mapping of event type to count.
        - _subjects_per_day: mapping from day string to a set of unique principal subjects.
        - _lock: threading.Lock used to protect concurrent updates.
        """
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
        """
        Record a single activity event for the current UTC day.
        
        Increments the in-memory counter for the given event_type for today's date and marks the principal as active for today. This operation is thread-safe.
        
        Parameters:
        	principal (Principal): The actor responsible for the event; its `subject` value is used to track unique active principals.
        	event_type (str): A short string identifying the type/category of the event.
        	details (str | None): Optional text included in the emitted log when provided; not stored in the aggregate counters.
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
        """
        Provide today's aggregated activity counters for dashboard display.
        
        Returns:
            dict[str, int]: A mapping with keys:
                - events_total: total number of events recorded today.
                - active_users_today: number of unique principals seen today.
                - distinct_event_types: number of distinct event types observed today.
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
        """
        Always reports that the in-memory activity store is ready.
        
        Returns:
            True: Indicates the in-memory store is ready.
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
        """
        Create a rollup store bound to the specified DynamoDB table.
        
        Parameters:
            table_name (str): DynamoDB table name used to store daily rollups.
            ddb_client (DynamoDbClientProtocol): Injected async DynamoDB client used for all table operations.
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
        """
        Record a single activity event and update daily rollup counters and markers.
        
        Parameters:
            principal (Principal): Authenticated caller whose `subject` identifies the actor.
            event_type (str): Event name used for per-type rollups and markers.
            details (str | None): Optional diagnostic context; sensitive values will be sanitized before logging.
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
        """Read current-day aggregate counters from DynamoDB."""
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
        """
        Check whether the configured DynamoDB rollup table can be queried.
        
        Returns:
            `true` if the rollup table can be queried, `false` otherwise.
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
        """
        Increment the specified numeric counter attribute on the DynamoDB item identified by `key`.
        
        Parameters:
            key (dict[str, dict[str, str]]): DynamoDB key object identifying the target item (e.g., {"pk": {"S": "..."}, "sk": {"S": "..."}}).
            counter_name (str): Name of the numeric attribute to increment on the item.
        """
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
        """
        Create a marker item in DynamoDB for the provided key only if an item with that primary key does not already exist.
        
        Parameters:
            key (dict[str, dict[str, str]]): DynamoDB item key attributes (e.g., {"pk": {"S": "..."}, "sk": {"S": "..."}}).
        
        Returns:
            bool: `True` if the marker item was created, `False` if an item already existed.
        
        Raises:
            ClientError, BotoCoreError: Propagates DynamoDB client errors except the conditional-failure that indicates the item already exists.
        """
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
