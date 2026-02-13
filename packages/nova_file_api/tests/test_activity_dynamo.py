from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError
from nova_file_api.activity import DynamoActivityStore
from nova_file_api.models import Principal


def _principal(*, subject: str) -> Principal:
    return Principal(
        subject=subject,
        scope_id="scope-1",
        tenant_id=None,
        scopes=(),
        permissions=(),
    )


def _conditional_check_failed(operation_name: str) -> ClientError:
    return ClientError(
        error_response={
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "conditional check failed",
            }
        },
        operation_name=operation_name,
    )


class _FakeDynamoDbClient:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], dict[str, dict[str, str]]] = {}

    def update_item(
        self,
        *,
        TableName: str,
        Key: dict[str, dict[str, str]],
        UpdateExpression: str,
        ExpressionAttributeNames: dict[str, str],
        ExpressionAttributeValues: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        del TableName, UpdateExpression
        pk = Key["pk"]["S"]
        sk = Key["sk"]["S"]
        key = (pk, sk)
        item = self._items.get(key, {"pk": {"S": pk}, "sk": {"S": sk}})

        updated_at_name = ExpressionAttributeNames["#updated_at"]
        item[updated_at_name] = ExpressionAttributeValues[":updated_at"]

        counter_alias = next(
            alias
            for alias in ExpressionAttributeNames
            if alias != "#updated_at"
        )
        counter_name = ExpressionAttributeNames[counter_alias]
        increment = int(
            next(
                value["N"]
                for token, value in ExpressionAttributeValues.items()
                if token != ":updated_at"
            )
        )
        current_value = int(item.get(counter_name, {"N": "0"})["N"])
        item[counter_name] = {"N": str(current_value + increment)}
        self._items[key] = item
        return {}

    def put_item(
        self,
        *,
        TableName: str,
        Item: dict[str, dict[str, str]],
        ConditionExpression: str,
    ) -> dict[str, Any]:
        del TableName
        key = (Item["pk"]["S"], Item["sk"]["S"])
        if (
            ConditionExpression == "attribute_not_exists(pk)"
            and key in self._items
        ):
            raise _conditional_check_failed("PutItem")
        self._items[key] = dict(Item)
        return {}

    def get_item(
        self,
        *,
        TableName: str,
        Key: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        del TableName
        key = (Key["pk"]["S"], Key["sk"]["S"])
        item = self._items.get(key)
        if item is None:
            return {}
        return {"Item": item}


def test_dynamo_activity_summary_counts_repeat_event_once() -> None:
    store = DynamoActivityStore(table_name="activity-rollups")
    store._ddb = _FakeDynamoDbClient()

    store.record(
        principal=_principal(subject="user-1"),
        event_type="uploads_initiate",
    )
    store.record(
        principal=_principal(subject="user-1"),
        event_type="uploads_initiate",
    )

    summary = store.summary()
    assert summary["events_total"] == 2
    assert summary["active_users_today"] == 1
    assert summary["distinct_event_types"] == 1


def test_dynamo_activity_summary_counts_new_event_types_and_users() -> None:
    store = DynamoActivityStore(table_name="activity-rollups")
    store._ddb = _FakeDynamoDbClient()

    store.record(
        principal=_principal(subject="user-1"),
        event_type="uploads_initiate",
    )
    store.record(
        principal=_principal(subject="user-2"),
        event_type="jobs_enqueue",
    )
    store.record(
        principal=_principal(subject="user-2"),
        event_type="jobs_enqueue",
    )

    summary = store.summary()
    assert summary["events_total"] == 3
    assert summary["active_users_today"] == 2
    assert summary["distinct_event_types"] == 2
