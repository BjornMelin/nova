from __future__ import annotations

import hashlib
from typing import Any, cast

from _pytest.logging import LogCaptureFixture
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


def _client_error(
    *,
    operation_name: str,
    code: str = "ConditionalCheckFailedException",
) -> ClientError:
    return ClientError(
        error_response={
            "Error": {
                "Code": code,
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
            raise _client_error(operation_name="PutItem")
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


class _FailingDynamoDbClient(_FakeDynamoDbClient):
    def __init__(
        self,
        *,
        update_failures: dict[int, Exception] | None = None,
        put_failures: dict[int, Exception] | None = None,
    ) -> None:
        """Inject failures for deterministic write-path testing."""
        super().__init__()
        self._update_failures = update_failures or {}
        self._put_failures = put_failures or {}
        self.update_item_calls = 0
        self.put_item_calls = 0

    def update_item(
        self,
        *,
        TableName: str,
        Key: dict[str, dict[str, str]],
        UpdateExpression: str,
        ExpressionAttributeNames: dict[str, str],
        ExpressionAttributeValues: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        self.update_item_calls += 1
        failure = self._update_failures.get(self.update_item_calls)
        if failure is not None:
            raise failure
        return super().update_item(
            TableName=TableName,
            Key=Key,
            UpdateExpression=UpdateExpression,
            ExpressionAttributeNames=ExpressionAttributeNames,
            ExpressionAttributeValues=ExpressionAttributeValues,
        )

    def put_item(
        self,
        *,
        TableName: str,
        Item: dict[str, dict[str, str]],
        ConditionExpression: str,
    ) -> dict[str, Any]:
        self.put_item_calls += 1
        failure = self._put_failures.get(self.put_item_calls)
        if failure is not None:
            raise failure
        return super().put_item(
            TableName=TableName,
            Item=Item,
            ConditionExpression=ConditionExpression,
        )


def _expected_principal_fingerprint(*, subject: str) -> str:
    return hashlib.sha256(subject.encode("utf-8")).hexdigest()[:16]


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


def test_dynamo_activity_record_logs_counter_failures_and_hides_principal(
    caplog: LogCaptureFixture,
) -> None:
    store = DynamoActivityStore(table_name="activity-rollups")
    store._ddb = _FailingDynamoDbClient(
        update_failures={
            1: _client_error(
                operation_name="UpdateItem",
            )
        }
    )
    principal = _principal(subject="user-1")

    with caplog.at_level("WARNING"):
        store.record(principal=principal, event_type="uploads_initiate")

    warning_records = [
        record
        for record in caplog.records
        if "activity rollup counter updates failed" in record.message
    ]
    assert len(warning_records) == 1
    warning_data = warning_records[0].__dict__
    assert (
        cast(str, warning_data["principal_fingerprint"])
        == _expected_principal_fingerprint(subject=principal.subject)
    )
    assert (
        "user-1" not in warning_records[0].getMessage()
        and principal.subject
        not in cast(str, warning_data["principal_fingerprint"])
    )


def test_dynamo_activity_record_user_marker_error_logs_warning(
    caplog: LogCaptureFixture,
) -> None:
    store = DynamoActivityStore(table_name="activity-rollups")
    store._ddb = _FailingDynamoDbClient(
        put_failures={
            1: _client_error(
                code="ProvisionedThroughputExceededException",
                operation_name="PutItem",
            ),
        }
    )
    principal = _principal(subject="user-2")

    with caplog.at_level("WARNING"):
        store.record(principal=principal, event_type="jobs_enqueue")

    warning_records = [
        record
        for record in caplog.records
        if "user marker write failed; skipping user marker accounting"
        in record.message
    ]
    assert len(warning_records) == 1
    warning_data = warning_records[0].__dict__
    assert (
        cast(str, warning_data["principal_fingerprint"])
        == _expected_principal_fingerprint(subject=principal.subject)
    )
    assert "user-2" not in warning_records[0].getMessage()


def test_dynamo_activity_record_distinct_event_type_increment_failure_logged(
    caplog: LogCaptureFixture,
) -> None:
    store = DynamoActivityStore(table_name="activity-rollups")
    store._ddb = _FailingDynamoDbClient(
        update_failures={
            4: _client_error(
                code="ProvisionedThroughputExceededException",
                operation_name="UpdateItem",
            )
        }
    )
    principal = _principal(subject="user-3")

    with caplog.at_level("WARNING"):
        store.record(principal=principal, event_type="jobs_complete")

    warning_records = [
        record
        for record in caplog.records
        if "activity distinct event-type increment failed" in record.message
    ]
    assert len(warning_records) == 1
    warning_data = warning_records[0].__dict__
    assert cast(str, warning_data["event_type"]) == "jobs_complete"
    assert cast(str, warning_data["error_type"]) == "ClientError"
    assert cast(str, warning_data["table"]) == "activity-rollups"
    assert "user-3" not in warning_records[0].getMessage()
