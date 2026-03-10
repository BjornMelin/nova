from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from botocore.exceptions import ClientError
from nova_file_api.jobs import DynamoJobRepository
from nova_file_api.models import JobRecord, JobStatus


class _FakeTable:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self.condition_writes: list[dict[str, Any]] = []
        self.query_error: ClientError | None = None
        self.query_calls: list[dict[str, Any]] = []

    async def put_item(
        self, *, Item: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        condition = kwargs.get("ConditionExpression")
        if condition is not None:
            self.condition_writes.append(
                {
                    "ConditionExpression": condition,
                    "ExpressionAttributeNames": kwargs.get(
                        "ExpressionAttributeNames", {}
                    ),
                    "ExpressionAttributeValues": kwargs.get(
                        "ExpressionAttributeValues", {}
                    ),
                }
            )
            expected_values = kwargs.get("ExpressionAttributeValues", {})
            expected_status = expected_values.get(":expected_status")
            job_id = str(Item["job_id"])
            existing = self._items.get(job_id)
            if existing is None or existing.get("status") != expected_status:
                raise ClientError(
                    error_response={
                        "Error": {"Code": "ConditionalCheckFailedException"}
                    },
                    operation_name="PutItem",
                )
        self._items[str(Item["job_id"])] = dict(Item)
        return {}

    async def get_item(self, *, Key: dict[str, Any]) -> dict[str, Any]:
        job_id = str(Key["job_id"])
        item = self._items.get(job_id)
        if item is None:
            return {}
        return {"Item": dict(item)}

    async def query(self, **kwargs: Any) -> dict[str, Any]:
        self.query_calls.append(kwargs)
        if self.query_error is not None:
            raise self.query_error
        assert kwargs["IndexName"] == "scope_id-created_at-index"
        assert kwargs.get("ScanIndexForward") is False
        return {"Items": []}


class _FakeDynamoResource:
    def __init__(self, table: _FakeTable) -> None:
        self._table = table

    async def Table(self, table_name: str) -> _FakeTable:
        del table_name
        return self._table


@pytest.fixture
def _fake_repo() -> tuple[DynamoJobRepository, _FakeTable]:
    table = _FakeTable()
    return (
        DynamoJobRepository(
            table_name="jobs-table",
            dynamodb_resource=_FakeDynamoResource(table),
        ),
        table,
    )


@pytest.mark.asyncio
async def test_dynamo_job_repository_create_get_update(
    _fake_repo: tuple[DynamoJobRepository, _FakeTable],
) -> None:
    repo, _table = _fake_repo
    del _table
    now = datetime.now(tz=UTC)
    record = JobRecord(
        job_id="job-dynamo-1",
        job_type="transform",
        scope_id="scope-1",
        status=JobStatus.PENDING,
        payload={"input": "value"},
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
    )

    await repo.create(record)
    loaded = await repo.get("job-dynamo-1")

    assert loaded is not None
    assert loaded.job_id == "job-dynamo-1"
    assert loaded.status == JobStatus.PENDING

    updated = loaded.model_copy(
        update={
            "status": JobStatus.SUCCEEDED,
            "result": {"accepted": True},
            "updated_at": datetime.now(tz=UTC),
        }
    )
    await repo.update(updated)

    loaded_updated = await repo.get("job-dynamo-1")
    assert loaded_updated is not None
    assert loaded_updated.status == JobStatus.SUCCEEDED
    assert loaded_updated.result == {"accepted": True}


@pytest.mark.asyncio
async def test_dynamo_job_repository_get_missing_returns_none(
    _fake_repo: tuple[DynamoJobRepository, _FakeTable],
) -> None:
    repo, _table = _fake_repo
    del _table
    assert await repo.get("missing") is None


@pytest.mark.asyncio
async def test_dynamo_job_repository_update_if_status_enforces_expected_state(
    _fake_repo: tuple[DynamoJobRepository, _FakeTable],
) -> None:
    repo, table = _fake_repo
    now = datetime.now(tz=UTC)
    pending = JobRecord(
        job_id="job-dynamo-2",
        job_type="transform",
        scope_id="scope-1",
        status=JobStatus.PENDING,
        payload={"input": "value"},
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
    )
    await repo.create(pending)

    succeeded = pending.model_copy(
        update={
            "status": JobStatus.SUCCEEDED,
            "result": {"accepted": True},
            "updated_at": datetime.now(tz=UTC),
        }
    )
    assert (
        await repo.update_if_status(
            record=succeeded,
            expected_status=JobStatus.PENDING,
        )
        is True
    )
    conditional_write = table.condition_writes[0]
    assert conditional_write["ConditionExpression"] == (
        "attribute_exists(job_id) AND #status = :expected_status"
    )
    assert conditional_write["ExpressionAttributeNames"] == {
        "#status": "status"
    }
    assert conditional_write["ExpressionAttributeValues"] == {
        ":expected_status": "pending"
    }
    assert (
        await repo.update_if_status(
            record=pending,
            expected_status=JobStatus.PENDING,
        )
        is False
    )


@pytest.mark.asyncio
async def test_dynamo_job_repository_list_for_scope_requires_gsi(
    _fake_repo: tuple[DynamoJobRepository, _FakeTable],
) -> None:
    repo, table = _fake_repo
    table.query_error = ClientError(
        error_response={
            "Error": {
                "Code": "ValidationException",
                "Message": (
                    "The table does not have the specified index: "
                    "scope_id-created_at-index"
                ),
            }
        },
        operation_name="Query",
    )

    with pytest.raises(
        RuntimeError,
        match="scope_id-created_at-index global secondary index",
    ):
        await repo.list_for_scope(scope_id="scope-1", limit=10)


@pytest.mark.asyncio
async def test_dynamo_job_repository_list_for_scope_reraises_validation_errors(
    _fake_repo: tuple[DynamoJobRepository, _FakeTable],
) -> None:
    repo, table = _fake_repo
    table.query_error = ClientError(
        error_response={
            "Error": {
                "Code": "ValidationException",
                "Message": "Query key condition not supported",
            }
        },
        operation_name="Query",
    )

    with pytest.raises(ClientError, match="Query key condition not supported"):
        await repo.list_for_scope(scope_id="scope-1", limit=10)


@pytest.mark.asyncio
async def test_dynamo_job_repository_list_for_scope_table_missing(
    _fake_repo: tuple[DynamoJobRepository, _FakeTable],
) -> None:
    repo, table = _fake_repo
    table.query_error = ClientError(
        error_response={"Error": {"Code": "ResourceNotFoundException"}},
        operation_name="Query",
    )

    with pytest.raises(
        RuntimeError,
        match="jobs table is not configured for scoped listing",
    ):
        await repo.list_for_scope(scope_id="scope-1", limit=10)
