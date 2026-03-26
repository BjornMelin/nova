"""In-memory DynamoDB doubles for idempotency-focused tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from botocore.exceptions import ClientError


def _conditional_check_failed() -> ClientError:
    return ClientError(
        error_response={
            "Error": {"Code": "ConditionalCheckFailedException", "Message": ""},
        },
        operation_name="ConditionCheck",
    )


class MemoryDynamoTable:
    """Deterministic in-memory table for idempotency records."""

    _PUT_CONDITION = (
        "attribute_not_exists(idempotency_key) OR expires_at <= :now"
    )
    _UPDATE_CONDITION = (
        "attribute_exists(idempotency_key) "
        "AND #state = :in_progress "
        "AND request_hash = :request_hash "
        "AND owner_token = :owner_token"
    )
    _DELETE_CONDITION = (
        "#state = :in_progress "
        "AND request_hash = :request_hash "
        "AND owner_token = :owner_token"
    )

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    async def get_item(self, **kwargs: object) -> dict[str, object]:
        """Return a copy of the stored item for the requested key.

        Args:
            **kwargs: DynamoDB-style keyword arguments containing ``Key``.

        Returns:
            dict[str, object]: ``{"Item": ...}`` when the key exists, otherwise
                an empty mapping.

        Raises:
            AssertionError: If ``Key["idempotency_key"]`` is not a string.
        """
        key = cast(dict[str, Any], kwargs["Key"])
        item_key = key["idempotency_key"]
        assert isinstance(item_key, str)
        item = self._items.get(item_key)
        return {"Item": deepcopy(item)} if item is not None else {}

    async def put_item(self, **kwargs: object) -> dict[str, object]:
        """Store a new item while honoring the supported conditional write.

        Args:
            **kwargs: DynamoDB-style keyword arguments containing ``Item`` and
                optional condition metadata.

        Returns:
            dict[str, object]: An empty mapping to mirror boto3 responses.

        Raises:
            AssertionError: If ``Item["idempotency_key"]`` is not a string.
            ClientError: If the supported conditional write fails.
            ValueError: If the requested condition expression is unsupported.
        """
        item = cast(dict[str, Any], kwargs["Item"])
        condition = kwargs.get("ConditionExpression")
        values = cast(
            dict[str, Any], kwargs.get("ExpressionAttributeValues", {})
        )
        item_key = item["idempotency_key"]
        assert isinstance(item_key, str)
        existing = self._items.get(item_key)

        if condition is not None and condition != self._PUT_CONDITION:
            raise ValueError(f"unsupported ConditionExpression: {condition!r}")
        if condition == self._PUT_CONDITION:
            now = values[":now"]
            assert isinstance(now, int)
            if existing is not None and int(existing["expires_at"]) > now:
                raise _conditional_check_failed()

        self._items[item_key] = deepcopy(item)
        return {}

    async def update_item(self, **kwargs: object) -> dict[str, object]:
        """Commit an in-progress idempotency record.

        Args:
            **kwargs: DynamoDB-style keyword arguments containing ``Key`` plus
                the supported conditional update payload.

        Returns:
            dict[str, object]: An empty mapping to mirror boto3 responses.

        Raises:
            AssertionError: If ``Key["idempotency_key"]`` is not a string.
            ClientError: If the conditional update fails.
            ValueError: If the requested condition expression is unsupported.
        """
        key = cast(dict[str, Any], kwargs["Key"])
        condition = kwargs.get("ConditionExpression")
        values = cast(dict[str, Any], kwargs["ExpressionAttributeValues"])
        item_key = key["idempotency_key"]
        assert isinstance(item_key, str)
        existing = self._items.get(item_key)
        if condition is not None and condition != self._UPDATE_CONDITION:
            raise ValueError(f"unsupported ConditionExpression: {condition!r}")
        if existing is None:
            raise _conditional_check_failed()
        if existing.get("state") != values[":in_progress"]:
            raise _conditional_check_failed()
        if existing.get("request_hash") != values[":request_hash"]:
            raise _conditional_check_failed()
        if existing.get("owner_token") != values[":owner_token"]:
            raise _conditional_check_failed()

        updated = deepcopy(existing)
        updated["state"] = values[":committed"]
        updated["response"] = deepcopy(values[":response"])
        updated["expires_at"] = values[":expires_at"]
        self._items[item_key] = updated
        return {}

    async def delete_item(self, **kwargs: object) -> dict[str, object]:
        """Delete an in-progress claim when the ownership check still matches.

        Args:
            **kwargs: DynamoDB-style keyword arguments containing ``Key`` plus
                the supported conditional delete payload.

        Returns:
            dict[str, object]: An empty mapping to mirror boto3 responses.

        Raises:
            AssertionError: If ``Key["idempotency_key"]`` is not a string.
            ClientError: If the conditional delete fails.
            ValueError: If the requested condition expression is unsupported.
        """
        key = cast(dict[str, Any], kwargs["Key"])
        condition = kwargs.get("ConditionExpression")
        values = cast(dict[str, Any], kwargs["ExpressionAttributeValues"])
        item_key = key["idempotency_key"]
        assert isinstance(item_key, str)
        existing = self._items.get(item_key)
        if condition is not None and condition != self._DELETE_CONDITION:
            raise ValueError(f"unsupported ConditionExpression: {condition!r}")
        if existing is None:
            raise _conditional_check_failed()
        if existing.get("state") != values[":in_progress"]:
            raise _conditional_check_failed()
        if existing.get("request_hash") != values[":request_hash"]:
            raise _conditional_check_failed()
        if existing.get("owner_token") != values[":owner_token"]:
            raise _conditional_check_failed()

        self._items.pop(item_key, None)
        return {}

    def put_raw(self, key: str, item: dict[str, Any]) -> None:
        """Install a raw item for focused test setup.

        Args:
            key: Table key used to store the raw item.
            item: Raw DynamoDB item payload to persist.

        Returns:
            None.
        """
        self._items[key] = deepcopy(item)

    def get_raw(self, key: str) -> dict[str, Any] | None:
        """Return the raw item stored for focused assertions.

        Args:
            key: Table key to fetch.

        Returns:
            dict[str, Any] | None: A deep copy of the stored item, if present.
        """
        item = self._items.get(key)
        return deepcopy(item) if item is not None else None


class MemoryDynamoResource:
    """Simple resource wrapper that returns one named table."""

    def __init__(
        self,
        *,
        tables: dict[str, MemoryDynamoTable] | None = None,
    ) -> None:
        self._tables = {} if tables is None else tables

    def Table(self, table_name: str) -> MemoryDynamoTable:
        """Return the named in-memory table, creating it on first access.

        Args:
            table_name: Name of the requested DynamoDB table.

        Returns:
            MemoryDynamoTable: Existing or newly created in-memory table.
        """
        table = self._tables.setdefault(table_name, MemoryDynamoTable())
        return table
