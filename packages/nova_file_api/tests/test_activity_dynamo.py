from __future__ import annotations

import hashlib
from typing import Any, cast

import pytest
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
        """
        Create an in-memory fake DynamoDB client and initialize its test state.
        
        Attributes:
            _items: Mapping from (pk, sk) tuple to a DynamoDB-style item map used to simulate stored table rows.
            put_conditions: List of ConditionExpression strings recorded from put_item calls.
        """
        self._items: dict[tuple[str, str], dict[str, dict[str, str]]] = {}
        self.put_conditions: list[str] = []

    async def update_item(
        self,
        *,
        TableName: str,
        Key: dict[str, dict[str, str]],
        UpdateExpression: str,
        ExpressionAttributeNames: dict[str, str],
        ExpressionAttributeValues: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        """
        Increment a numeric attribute and update the item's timestamp in the in-memory store identified by the provided key.
        
        Parameters:
            Key (dict[str, dict[str, str]]): Primary key with structure {"pk": {"S": "<pk>"}, "sk": {"S": "<sk>"}} identifying the item.
            ExpressionAttributeNames (dict[str, str]): Mapping of expression aliases (e.g. "#counter", "#updated_at") to attribute names; one alias must map to the updated-at attribute.
            ExpressionAttributeValues (dict[str, dict[str, str]]): Mapping of value tokens where one token is ":updated_at" (a value map) and one token is a numeric value with key "N" used to increment the counter.
        
        Returns:
            dict: An empty dict to simulate DynamoDB's empty response body.
        """
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

    async def put_item(
        self,
        *,
        TableName: str,
        Item: dict[str, dict[str, str]],
        ConditionExpression: str,
    ) -> dict[str, Any]:
        """
        Store the provided item in the in-memory table and record the provided condition expression.
        
        The Item is expected to be a DynamoDB-style attribute map (e.g., {"pk": {"S": "value"}, "sk": {"S": "value"}, ...}).
        The ConditionExpression is appended to the client's put_conditions list. If ConditionExpression is
        "attribute_not_exists(pk)" and an item with the same (pk, sk) already exists, a ClientError is raised to
        simulate DynamoDB's conditional write failure.
        
        Parameters:
            Item (dict): DynamoDB-style item map; must contain "pk" and "sk" string attributes.
            ConditionExpression (str): Conditional expression applied to the put operation.
        
        Returns:
            dict: An empty response map, simulating a successful PutItem response.
        
        Raises:
            botocore.exceptions.ClientError: If ConditionExpression == "attribute_not_exists(pk)" and the key exists.
        """
        del TableName
        self.put_conditions.append(ConditionExpression)
        key = (Item["pk"]["S"], Item["sk"]["S"])
        if (
            ConditionExpression == "attribute_not_exists(pk)"
            and key in self._items
        ):
            raise _client_error(operation_name="PutItem")
        self._items[key] = dict(Item)
        return {}

    async def get_item(
        self,
        *,
        TableName: str,
        Key: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        """
        Retrieve an item by its primary key from the in-memory DynamoDB-like store.
        
        Parameters:
            TableName (str): Ignored; present for API compatibility.
            Key (dict[str, dict[str, str]]): DynamoDB-style key with string attributes; must contain
                {'pk': {'S': primary_key}, 'sk': {'S': sort_key}}.
        
        Returns:
            dict: An empty dict if no item is found; otherwise a dict with the stored item under the
            "Item" key (e.g., {"Item": {...}}).
        """
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
        """
        Configure the instance to inject deterministic failures into UpdateItem and PutItem calls.
        
        Parameters:
            update_failures (dict[int, Exception] | None): Mapping from 1-based UpdateItem call index to the Exception to raise for that call. If None, no UpdateItem failures are injected.
            put_failures (dict[int, Exception] | None): Mapping from 1-based PutItem call index to the Exception to raise for that call. If None, no PutItem failures are injected.
        
        The constructor stores the provided failure maps and initializes the counters `update_item_calls` and `put_item_calls` to zero.
        """
        super().__init__()
        self._update_failures = update_failures or {}
        self._put_failures = put_failures or {}
        self.update_item_calls = 0
        self.put_item_calls = 0

    async def update_item(
        self,
        *,
        TableName: str,
        Key: dict[str, dict[str, str]],
        UpdateExpression: str,
        ExpressionAttributeNames: dict[str, str],
        ExpressionAttributeValues: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        """
        Invoke an UpdateItem on the fake client, optionally injecting a preconfigured failure for this call.
        
        If a failure is configured for the current 1-based update call count, that exception is raised instead of performing the update. Otherwise the call is forwarded to the superclass implementation and its response is returned.
        
        Returns:
            dict[str, Any]: The response returned by the underlying client's update_item.
        
        Raises:
            Exception: The configured failure for this call index, if present.
        """
        self.update_item_calls += 1
        failure = self._update_failures.get(self.update_item_calls)
        if failure is not None:
            raise failure
        return await super().update_item(
            TableName=TableName,
            Key=Key,
            UpdateExpression=UpdateExpression,
            ExpressionAttributeNames=ExpressionAttributeNames,
            ExpressionAttributeValues=ExpressionAttributeValues,
        )

    async def put_item(
        self,
        *,
        TableName: str,
        Item: dict[str, dict[str, str]],
        ConditionExpression: str,
    ) -> dict[str, Any]:
        """
        Simulate a DynamoDB PutItem call for tests, tracking call count and optionally raising an injected failure.
        
        Parameters:
            TableName (str): The target table name.
            Item (dict[str, dict[str, str]]): DynamoDB-style attribute map to put.
            ConditionExpression (str): Conditional expression applied to the put.
        
        Returns:
            dict[str, Any]: The DynamoDB-style response returned by the underlying put_item implementation.
        
        Raises:
            Exception: The configured failure for the current call index, if one has been injected.
        """
        self.put_item_calls += 1
        failure = self._put_failures.get(self.put_item_calls)
        if failure is not None:
            raise failure
        return await super().put_item(
            TableName=TableName,
            Item=Item,
            ConditionExpression=ConditionExpression,
        )


def _expected_principal_fingerprint(*, subject: str) -> str:
    """
    Compute a 16-character lowercase SHA-256 hex fingerprint of a principal subject.
    
    Parameters:
        subject (str): Principal subject string to fingerprint.
    
    Returns:
        str: 16-character lowercase hexadecimal string produced from the SHA-256 digest of `subject`.
    """
    return hashlib.sha256(subject.encode("utf-8")).hexdigest()[:16]


@pytest.mark.asyncio
async def test_dynamo_activity_store_uses_injected_client_without_boto3() -> (
    None
):
    store = DynamoActivityStore(
        table_name="activity-rollups",
        ddb_client=_FakeDynamoDbClient(),
    )
    await store.record(
        principal=_principal(subject="user-1"),
        event_type="uploads_initiate",
    )

    summary = await store.summary()
    assert summary["events_total"] == 1


@pytest.mark.asyncio
async def test_dynamo_activity_summary_counts_repeat_event_once() -> None:
    store = DynamoActivityStore(
        table_name="activity-rollups",
        ddb_client=_FakeDynamoDbClient(),
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


@pytest.mark.asyncio
async def test_dynamo_activity_summary_counts_new_event_types_and_users() -> (
    None
):
    store = DynamoActivityStore(
        table_name="activity-rollups",
        ddb_client=_FakeDynamoDbClient(),
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


@pytest.mark.asyncio
async def test_dynamo_activity_store_uses_conditional_first_seen_markers() -> (
    None
):
    client = _FakeDynamoDbClient()
    store = DynamoActivityStore(
        table_name="activity-rollups",
        ddb_client=client,
    )

    await store.record(
        principal=_principal(subject="user-1"),
        event_type="uploads_initiate",
    )
    await store.record(
        principal=_principal(subject="user-1"),
        event_type="uploads_initiate",
    )

    assert client.put_conditions
    assert all(
        condition == "attribute_not_exists(pk)"
        for condition in client.put_conditions
    )


@pytest.mark.asyncio
async def test_dynamo_activity_record_logs_counter_failures_and_hides_principal(
    caplog: LogCaptureFixture,
) -> None:
    store = DynamoActivityStore(
        table_name="activity-rollups",
        ddb_client=_FailingDynamoDbClient(
            update_failures={
                1: _client_error(
                    operation_name="UpdateItem",
                )
            }
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


@pytest.mark.asyncio
async def test_dynamo_activity_record_user_marker_error_logs_warning(
    caplog: LogCaptureFixture,
) -> None:
    store = DynamoActivityStore(
        table_name="activity-rollups",
        ddb_client=_FailingDynamoDbClient(
            put_failures={
                1: _client_error(
                    code="ProvisionedThroughputExceededException",
                    operation_name="PutItem",
                ),
            }
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


@pytest.mark.asyncio
async def test_dynamo_activity_record_event_type_increment_failure_logged(
    caplog: LogCaptureFixture,
) -> None:
    store = DynamoActivityStore(
        table_name="activity-rollups",
        ddb_client=_FailingDynamoDbClient(
            update_failures={
                4: _client_error(
                    code="ProvisionedThroughputExceededException",
                    operation_name="UpdateItem",
                )
            }
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