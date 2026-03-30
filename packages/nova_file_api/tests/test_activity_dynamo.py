from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest
from _pytest.logging import LogCaptureFixture
from botocore.exceptions import ClientError
from nova_file_api.activity import DynamoActivityStore, DynamoTable
from nova_file_api.config import Settings
from nova_file_api.dependencies import build_activity_store
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


class _FakeDynamoDbTable:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], dict[str, object]] = {}
        self.put_conditions: list[str] = []

    async def update_item(
        self,
        **kwargs: object,
    ) -> dict[str, Any]:
        Key = cast(dict[str, str], kwargs["Key"])
        UpdateExpression = cast(str, kwargs["UpdateExpression"])
        ExpressionAttributeNames = cast(
            dict[str, str], kwargs["ExpressionAttributeNames"]
        )
        ExpressionAttributeValues = cast(
            dict[str, object], kwargs["ExpressionAttributeValues"]
        )
        del UpdateExpression
        pk = Key["pk"]
        sk = Key["sk"]
        key = (pk, sk)
        item = self._items.get(key, {"pk": pk, "sk": sk})

        updated_at_name = ExpressionAttributeNames["#updated_at"]
        item[updated_at_name] = ExpressionAttributeValues[":updated_at"]

        counter_alias = next(
            alias
            for alias in ExpressionAttributeNames
            if alias != "#updated_at"
        )
        counter_name = ExpressionAttributeNames[counter_alias]
        increment_value = cast(
            int | str, ExpressionAttributeValues[":increment"]
        )
        increment = int(increment_value)
        current_value = int(cast(int | str, item.get(counter_name, 0)))
        item[counter_name] = current_value + increment
        self._items[key] = item
        return {}

    async def put_item(self, **kwargs: object) -> dict[str, Any]:
        Item = cast(dict[str, object], kwargs["Item"])
        ConditionExpression = cast(str, kwargs["ConditionExpression"])
        self.put_conditions.append(ConditionExpression)
        key = (str(Item["pk"]), str(Item["sk"]))
        if (
            ConditionExpression == "attribute_not_exists(pk)"
            and key in self._items
        ):
            raise _client_error(operation_name="PutItem")
        self._items[key] = dict(Item)
        return {}

    async def get_item(self, **kwargs: object) -> dict[str, Any]:
        Key = cast(dict[str, str], kwargs["Key"])
        key = (Key["pk"], Key["sk"])
        item = self._items.get(key)
        if item is None:
            return {}
        return {"Item": item}


class _FailingDynamoDbTable(_FakeDynamoDbTable):
    def __init__(
        self,
        *,
        update_failures: dict[int, Exception] | None = None,
        put_failures: dict[int, Exception] | None = None,
        get_failures: dict[int, Exception] | None = None,
    ) -> None:
        """Inject failures for deterministic read and write-path testing."""
        super().__init__()
        self._update_failures = update_failures or {}
        self._put_failures = put_failures or {}
        self._get_failures = get_failures or {}
        self.update_item_calls = 0
        self.put_item_calls = 0
        self.get_item_calls = 0

    async def update_item(
        self,
        **kwargs: object,
    ) -> dict[str, Any]:
        self.update_item_calls += 1
        failure = self._update_failures.get(self.update_item_calls)
        if failure is not None:
            raise failure
        return await super().update_item(**kwargs)

    async def put_item(self, **kwargs: object) -> dict[str, Any]:
        self.put_item_calls += 1
        failure = self._put_failures.get(self.put_item_calls)
        if failure is not None:
            raise failure
        return await super().put_item(**kwargs)

    async def get_item(self, **kwargs: object) -> dict[str, Any]:
        self.get_item_calls += 1
        failure = self._get_failures.get(self.get_item_calls)
        if failure is not None:
            raise failure
        return await super().get_item(**kwargs)


class _FakeDynamoDbResource:
    def __init__(self, table: _FakeDynamoDbTable) -> None:
        self._table = table
        self.last_table_name: str | None = None
        self.meta = SimpleNamespace(client=object())

    def Table(self, table_name: str) -> DynamoTable:
        self.last_table_name = table_name
        return self._table


def _expected_principal_fingerprint(*, subject: str) -> str:
    return hashlib.sha256(subject.encode("utf-8")).hexdigest()[:16]


@pytest.mark.anyio
async def test_dynamo_activity_store_uses_injected_table_without_boto3() -> (
    None
):
    store = DynamoActivityStore(
        table_name="activity-rollups",
        dynamodb_resource=_FakeDynamoDbResource(_FakeDynamoDbTable()),
    )
    await store.record(
        principal=_principal(subject="user-1"),
        event_type="uploads_initiate",
    )

    summary = await store.summary()
    assert summary["events_total"] == 1


@pytest.mark.anyio
async def test_dynamo_activity_summary_counts_repeat_event_once() -> None:
    store = DynamoActivityStore(
        table_name="activity-rollups",
        dynamodb_resource=_FakeDynamoDbResource(_FakeDynamoDbTable()),
    )

    await store.record(
        principal=_principal(subject="user-1"),
        event_type="uploads_initiate",
    )
    await store.record(
        principal=_principal(subject="user-1"),
        event_type="uploads_initiate",
    )

    summary = await store.summary()
    assert summary["events_total"] == 2
    assert summary["active_users_today"] == 1
    assert summary["distinct_event_types"] == 1


@pytest.mark.anyio
async def test_dynamo_activity_summary_counts_new_event_types_and_users() -> (
    None
):
    store = DynamoActivityStore(
        table_name="activity-rollups",
        dynamodb_resource=_FakeDynamoDbResource(_FakeDynamoDbTable()),
    )

    await store.record(
        principal=_principal(subject="user-1"),
        event_type="uploads_initiate",
    )
    await store.record(
        principal=_principal(subject="user-2"),
        event_type="jobs_enqueue",
    )
    await store.record(
        principal=_principal(subject="user-2"),
        event_type="jobs_enqueue",
    )

    summary = await store.summary()
    assert summary["events_total"] == 3
    assert summary["active_users_today"] == 2
    assert summary["distinct_event_types"] == 2


@pytest.mark.anyio
async def test_dynamo_activity_summary_accepts_decimal_counters() -> None:
    table = _FakeDynamoDbTable()
    store = DynamoActivityStore(
        table_name="activity-rollups",
        dynamodb_resource=_FakeDynamoDbResource(table),
    )
    day_key = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    table._items[(f"ROLLUP#{day_key}", "SUMMARY")] = {
        "pk": f"ROLLUP#{day_key}",
        "sk": "SUMMARY",
        "events_total": Decimal("3"),
        "active_users_today": Decimal("2"),
        "distinct_event_types": Decimal("1"),
    }

    summary = await store.summary()

    assert summary == {
        "events_total": 3,
        "active_users_today": 2,
        "distinct_event_types": 1,
    }


@pytest.mark.anyio
async def test_dynamo_activity_summary_ignores_malformed_counters() -> None:
    day_key = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    table = _FakeDynamoDbTable()
    store = DynamoActivityStore(
        table_name="activity-rollups",
        dynamodb_resource=_FakeDynamoDbResource(table),
    )
    table._items[(f"ROLLUP#{day_key}", "SUMMARY")] = {
        "pk": f"ROLLUP#{day_key}",
        "sk": "SUMMARY",
        "events_total": Decimal("NaN"),
        "active_users_today": "3.5",
        "distinct_event_types": object(),
    }

    summary = await store.summary()

    assert summary == {
        "events_total": 0,
        "active_users_today": 0,
        "distinct_event_types": 0,
    }


@pytest.mark.anyio
@pytest.mark.runtime_gate
async def test_dynamo_activity_store_uses_conditional_first_seen_markers() -> (
    None
):
    table = _FakeDynamoDbTable()
    store = DynamoActivityStore(
        table_name="activity-rollups",
        dynamodb_resource=_FakeDynamoDbResource(table),
    )

    await store.record(
        principal=_principal(subject="user-1"),
        event_type="uploads_initiate",
    )
    await store.record(
        principal=_principal(subject="user-1"),
        event_type="uploads_initiate",
    )

    assert table.put_conditions
    assert all(
        condition == "attribute_not_exists(pk)"
        for condition in table.put_conditions
    )


@pytest.mark.anyio
async def test_dynamo_activity_record_logs_counter_failures_and_hides_principal(
    caplog: LogCaptureFixture,
) -> None:
    store = DynamoActivityStore(
        table_name="activity-rollups",
        dynamodb_resource=_FakeDynamoDbResource(
            _FailingDynamoDbTable(
                update_failures={
                    1: _client_error(
                        operation_name="UpdateItem",
                    )
                }
            )
        ),
    )
    principal = _principal(subject="user-1")

    with caplog.at_level("WARNING"):
        await store.record(principal=principal, event_type="uploads_initiate")

    warning_records = [
        record
        for record in caplog.records
        if "activity rollup counter updates failed" in record.message
    ]
    assert len(warning_records) == 1
    warning_data = warning_records[0].__dict__
    assert cast(
        str, warning_data["principal_fingerprint"]
    ) == _expected_principal_fingerprint(subject=principal.subject)
    assert "user-1" not in warning_records[0].getMessage()
    assert principal.subject not in cast(
        str, warning_data["principal_fingerprint"]
    )


@pytest.mark.anyio
async def test_dynamo_activity_record_user_marker_error_logs_warning(
    caplog: LogCaptureFixture,
) -> None:
    store = DynamoActivityStore(
        table_name="activity-rollups",
        dynamodb_resource=_FakeDynamoDbResource(
            _FailingDynamoDbTable(
                put_failures={
                    1: _client_error(
                        code="ProvisionedThroughputExceededException",
                        operation_name="PutItem",
                    ),
                }
            )
        ),
    )
    principal = _principal(subject="user-2")

    with caplog.at_level("WARNING"):
        await store.record(principal=principal, event_type="jobs_enqueue")

    warning_records = [
        record
        for record in caplog.records
        if "user marker write failed; skipping user marker accounting"
        in record.message
    ]
    assert len(warning_records) == 1
    warning_data = warning_records[0].__dict__
    assert cast(
        str, warning_data["principal_fingerprint"]
    ) == _expected_principal_fingerprint(subject=principal.subject)
    assert "user-2" not in warning_records[0].getMessage()


@pytest.mark.anyio
async def test_dynamo_activity_record_event_type_increment_failure_logged(
    caplog: LogCaptureFixture,
) -> None:
    store = DynamoActivityStore(
        table_name="activity-rollups",
        dynamodb_resource=_FakeDynamoDbResource(
            _FailingDynamoDbTable(
                update_failures={
                    4: _client_error(
                        code="ProvisionedThroughputExceededException",
                        operation_name="UpdateItem",
                    )
                }
            )
        ),
    )
    principal = _principal(subject="user-3")

    with caplog.at_level("WARNING"):
        await store.record(principal=principal, event_type="jobs_complete")

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


@pytest.mark.anyio
async def test_dynamo_activity_healthcheck_logs_and_fails_closed() -> None:
    store = DynamoActivityStore(
        table_name="activity-rollups",
        dynamodb_resource=_FakeDynamoDbResource(
            _FailingDynamoDbTable(
                get_failures={
                    1: _client_error(
                        code="ResourceNotFoundException",
                        operation_name="GetItem",
                    )
                }
            )
        ),
    )

    assert await store.healthcheck() is False


@pytest.mark.anyio
async def test_build_activity_store_uses_dynamodb_resource_table() -> None:
    table = _FakeDynamoDbTable()
    resource = _FakeDynamoDbResource(table)
    settings = Settings.model_validate(
        {
            "ACTIVITY_STORE_BACKEND": "dynamodb",
            "ACTIVITY_ROLLUPS_TABLE": "activity-rollups",
            "IDEMPOTENCY_ENABLED": "false",
        }
    )

    store = build_activity_store(
        settings=settings,
        dynamodb_resource=resource,
    )

    assert isinstance(store, DynamoActivityStore)
    await store.record(
        principal=_principal(subject="user-4"),
        event_type="exports_list",
    )
    assert resource.last_table_name == "activity-rollups"
