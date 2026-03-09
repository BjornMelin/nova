from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest
from botocore.exceptions import ClientError
from nova_file_api.jobs import DynamoJobRepository
from nova_file_api.models import JobRecord, JobStatus


class _FakeTable:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self.condition_writes: list[dict[str, Any]] = []

    def put_item(
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

    def get_item(self, *, Key: dict[str, Any]) -> dict[str, Any]:
        job_id = str(Key["job_id"])
        item = self._items.get(job_id)
        if item is None:
            return {}
        return {"Item": dict(item)}


class _FakeDynamoResource:
    def __init__(self, table: _FakeTable) -> None:
        self._table = table

    def Table(self, table_name: str) -> _FakeTable:
        del table_name
        return self._table


@pytest.fixture
def _fake_repo(monkeypatch: pytest.MonkeyPatch) -> DynamoJobRepository:
    table = _FakeTable()

    def _resource(service_name: str) -> _FakeDynamoResource:
        assert service_name == "dynamodb"
        return _FakeDynamoResource(table)

    monkeypatch.setattr(
        "nova_file_api.jobs_repository.boto3.resource", _resource
    )
    return DynamoJobRepository(table_name="jobs-table")


def test_dynamo_job_repository_create_get_update(
    _fake_repo: DynamoJobRepository,
) -> None:
    now = datetime.now(tz=UTC)
    record = JobRecord(
        job_id="job-dynamo-1",
        job_type="transfer.process",
        scope_id="scope-1",
        status=JobStatus.PENDING,
        payload={"input": "value"},
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
    )

    _fake_repo.create(record)
    loaded = _fake_repo.get("job-dynamo-1")

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
    _fake_repo.update(updated)

    loaded_updated = _fake_repo.get("job-dynamo-1")
    assert loaded_updated is not None
    assert loaded_updated.status == JobStatus.SUCCEEDED
    assert loaded_updated.result == {"accepted": True}


def test_dynamo_job_repository_get_missing_returns_none(
    _fake_repo: DynamoJobRepository,
) -> None:
    assert _fake_repo.get("missing") is None


def test_dynamo_job_repository_update_if_status_enforces_expected_state(
    _fake_repo: DynamoJobRepository,
) -> None:
    now = datetime.now(tz=UTC)
    pending = JobRecord(
        job_id="job-dynamo-2",
        job_type="transfer.process",
        scope_id="scope-1",
        status=JobStatus.PENDING,
        payload={"input": "value"},
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
    )
    _fake_repo.create(pending)

    succeeded = pending.model_copy(
        update={
            "status": JobStatus.SUCCEEDED,
            "result": {"accepted": True},
            "updated_at": datetime.now(tz=UTC),
        }
    )
    assert (
        _fake_repo.update_if_status(
            record=succeeded,
            expected_status=JobStatus.PENDING,
        )
        is True
    )
    table = cast(_FakeTable, _fake_repo._table)
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
        _fake_repo.update_if_status(
            record=pending,
            expected_status=JobStatus.PENDING,
        )
        is False
    )
