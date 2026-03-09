"""Async job repository backends and serialization helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Protocol

import boto3
from botocore.exceptions import ClientError

from nova_file_api.models import JobRecord, JobStatus


class JobRepository(Protocol):
    """Persist and retrieve job records."""

    def create(self, record: JobRecord) -> None:
        """Persist a new job record."""

    def get(self, job_id: str) -> JobRecord | None:
        """Return job record by id if present."""

    def update(self, record: JobRecord) -> None:
        """Replace a job record."""

    def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        """Replace record only when current status matches expected value."""

    def list_for_scope(self, *, scope_id: str, limit: int) -> list[JobRecord]:
        """List jobs visible to the provided caller scope."""


@dataclass(slots=True)
class MemoryJobRepository:
    """In-memory job record repository."""

    _records: dict[str, JobRecord]
    _lock: Lock = field(init=False, repr=False)

    def __init__(self) -> None:
        """Initialize empty in-memory record storage."""
        self._records = {}
        self._lock = Lock()

    def create(self, record: JobRecord) -> None:
        """Persist a new in-memory job record."""
        with self._lock:
            self._records[record.job_id] = record

    def get(self, job_id: str) -> JobRecord | None:
        """Return an in-memory job record by ID when present."""
        with self._lock:
            return self._records.get(job_id)

    def update(self, record: JobRecord) -> None:
        """Replace an existing in-memory job record."""
        with self._lock:
            self._records[record.job_id] = record

    def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        """Replace one record only when its current status still matches."""
        with self._lock:
            current = self._records.get(record.job_id)
            if current is None or current.status != expected_status:
                return False
            self._records[record.job_id] = record
            return True

    def list_for_scope(self, *, scope_id: str, limit: int) -> list[JobRecord]:
        """List caller-owned in-memory jobs newest first."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        with self._lock:
            records = [
                record
                for record in self._records.values()
                if record.scope_id == scope_id
            ]
        records.sort(key=lambda record: record.created_at, reverse=True)
        return records[:limit]


@dataclass(slots=True)
class DynamoJobRepository:
    """DynamoDB-backed job record repository."""

    SCOPE_CREATED_AT_INDEX = "scope_id-created_at-index"

    table_name: str
    _table: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Bind the DynamoDB table resource after construction."""
        self._table = boto3.resource("dynamodb").Table(self.table_name)

    def create(self, record: JobRecord) -> None:
        """Persist a job record in DynamoDB."""
        self._table.put_item(Item=record_to_item(record))

    def get(self, job_id: str) -> JobRecord | None:
        """Return a DynamoDB job record by ID when present."""
        response = self._table.get_item(Key={"job_id": job_id})
        item = response.get("Item")
        if item is None:
            return None
        return item_to_record(item)

    def update(self, record: JobRecord) -> None:
        """Replace an existing DynamoDB job record."""
        self._table.put_item(Item=record_to_item(record))

    def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        """Replace one record only when its stored status still matches."""
        try:
            self._table.put_item(
                Item=record_to_item(record),
                ConditionExpression=(
                    "attribute_exists(job_id) AND #status = :expected_status"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":expected_status": expected_status.value
                },
            )
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code == "ConditionalCheckFailedException":
                return False
            raise
        return True

    def list_for_scope(self, *, scope_id: str, limit: int) -> list[JobRecord]:
        """List caller-owned DynamoDB jobs newest first."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        items: list[dict[str, Any]] = []
        last_evaluated_key: dict[str, Any] | None = None
        remaining = limit
        while True:
            query_kwargs: dict[str, Any] = {
                "IndexName": self.SCOPE_CREATED_AT_INDEX,
                "KeyConditionExpression": "#scope_id = :scope_id",
                "ExpressionAttributeNames": {"#scope_id": "scope_id"},
                "ExpressionAttributeValues": {":scope_id": scope_id},
                "Limit": remaining,
                "ScanIndexForward": False,
            }
            if last_evaluated_key is not None:
                query_kwargs["ExclusiveStartKey"] = last_evaluated_key

            try:
                response = self._table.query(**query_kwargs)
            except ClientError as exc:
                error_code = str(exc.response.get("Error", {}).get("Code", ""))
                if error_code in {
                    "ValidationException",
                    "ResourceNotFoundException",
                }:
                    raise RuntimeError(
                        "DynamoDB jobs repository requires the "
                        f"{self.SCOPE_CREATED_AT_INDEX} index"
                    ) from exc
                raise
            items.extend(response.get("Items", []))
            last_evaluated_key = response.get("LastEvaluatedKey")
            remaining = limit - len(items)
            if last_evaluated_key is None or remaining <= 0:
                break
        return [item_to_record(item) for item in items[:limit]]


def record_to_item(record: JobRecord) -> dict[str, Any]:
    """Serialize JobRecord to a DynamoDB-friendly item."""
    return record.model_dump(mode="json")


def item_to_record(item: dict[str, Any]) -> JobRecord:
    """Deserialize a DynamoDB item into a JobRecord."""
    return JobRecord.model_validate(item)
