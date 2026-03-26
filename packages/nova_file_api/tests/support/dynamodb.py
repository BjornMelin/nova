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

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    async def get_item(self, **kwargs: object) -> dict[str, object]:
        key = cast(dict[str, Any], kwargs["Key"])
        item_key = key["idempotency_key"]
        assert isinstance(item_key, str)
        item = self._items.get(item_key)
        return {"Item": deepcopy(item)} if item is not None else {}

    async def put_item(self, **kwargs: object) -> dict[str, object]:
        item = cast(dict[str, Any], kwargs["Item"])
        condition = kwargs.get("ConditionExpression")
        values = cast(
            dict[str, Any], kwargs.get("ExpressionAttributeValues", {})
        )
        item_key = item["idempotency_key"]
        assert isinstance(item_key, str)
        existing = self._items.get(item_key)

        if (
            condition
            == "attribute_not_exists(idempotency_key) OR expires_at <= :now"
        ):
            now = values[":now"]
            assert isinstance(now, int)
            if existing is not None and int(existing["expires_at"]) > now:
                raise _conditional_check_failed()

        self._items[item_key] = deepcopy(item)
        return {}

    async def update_item(self, **kwargs: object) -> dict[str, object]:
        key = cast(dict[str, Any], kwargs["Key"])
        values = cast(dict[str, Any], kwargs["ExpressionAttributeValues"])
        item_key = key["idempotency_key"]
        assert isinstance(item_key, str)
        existing = self._items.get(item_key)
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
        key = cast(dict[str, Any], kwargs["Key"])
        values = cast(dict[str, Any], kwargs["ExpressionAttributeValues"])
        item_key = key["idempotency_key"]
        assert isinstance(item_key, str)
        existing = self._items.get(item_key)
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
        """Install raw state for focused tests."""
        self._items[key] = deepcopy(item)

    def get_raw(self, key: str) -> dict[str, Any] | None:
        """Return raw state for focused assertions."""
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
        table = self._tables.setdefault(table_name, MemoryDynamoTable())
        return table
