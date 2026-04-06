"""Unit tests for export service status-update adapter semantics."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from botocore.exceptions import ClientError

from nova_file_api.errors import FileTransferError
from nova_file_api.export_models import ExportRecord, ExportStatus
from nova_file_api.export_runtime import (
    DynamoExportRepository,
    MemoryExportRepository,
)
from nova_file_api.exports import ExportService, MemoryExportPublisher
from nova_runtime_support.metrics import MetricsCollector


class _RecordingExportPublisher(MemoryExportPublisher):
    def __init__(self) -> None:
        super().__init__(process_immediately=False)
        self.stop_calls: list[dict[str, str]] = []

    async def publish(self, *, export: ExportRecord) -> str | None:
        del export
        return "arn:aws:states:::execution:test"

    async def stop_execution(self, *, execution_arn: str, cause: str) -> None:
        self.stop_calls.append({"execution_arn": execution_arn, "cause": cause})


class _EventuallyConsistentExportTable:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self.get_item_calls: list[dict[str, Any]] = []
        self.put_item_calls: list[dict[str, Any]] = []
        self.query_calls: list[dict[str, Any]] = []

    async def put_item(self, **kwargs: object) -> dict[str, object]:
        item = deepcopy(cast(dict[str, Any], kwargs["Item"]))
        export_id = item["export_id"]
        assert isinstance(export_id, str)
        condition = kwargs.get("ConditionExpression")
        if condition is not None:
            existing = self._items.get(export_id)
            if existing is None:
                raise ClientError(
                    error_response={
                        "Error": {
                            "Code": "ConditionalCheckFailedException",
                            "Message": "",
                        }
                    },
                    operation_name="PutItem",
                )
            values = cast(dict[str, Any], kwargs["ExpressionAttributeValues"])
            if existing.get("status") != values[":expected_status"]:
                raise ClientError(
                    error_response={
                        "Error": {
                            "Code": "ConditionalCheckFailedException",
                            "Message": "",
                        }
                    },
                    operation_name="PutItem",
                )
        self.put_item_calls.append(deepcopy(dict(kwargs)))
        self._items[export_id] = item
        return {}

    async def get_item(self, **kwargs: object) -> dict[str, object]:
        self.get_item_calls.append(deepcopy(dict(kwargs)))
        key = cast(dict[str, Any], kwargs["Key"])
        export_id = key["export_id"]
        assert isinstance(export_id, str)
        item = self._items.get(export_id)
        if item is None:
            return {}
        if not kwargs.get("ConsistentRead"):
            return {}
        return {"Item": deepcopy(item)}

    async def query(self, **kwargs: object) -> dict[str, object]:
        self.query_calls.append(deepcopy(dict(kwargs)))
        values = cast(dict[str, Any], kwargs["ExpressionAttributeValues"])
        scope_id = values[":scope_id"]
        assert isinstance(scope_id, str)
        items = [
            deepcopy(item)
            for item in self._items.values()
            if item.get("scope_id") == scope_id
        ]
        items.sort(key=lambda item: item["created_at"], reverse=True)
        limit = kwargs.get("Limit")
        if isinstance(limit, int):
            items = items[:limit]
        return {"Items": items}


class _EventuallyConsistentExportResource:
    def __init__(self, table: _EventuallyConsistentExportTable) -> None:
        self.table = table

    def Table(self, table_name: str) -> _EventuallyConsistentExportTable:
        assert table_name == "exports"
        return self.table


def _dynamo_export_service(
    *,
    publisher: MemoryExportPublisher | None = None,
) -> tuple[ExportService, _EventuallyConsistentExportTable]:
    table = _EventuallyConsistentExportTable()
    repository = DynamoExportRepository(
        table_name="exports",
        dynamodb_resource=_EventuallyConsistentExportResource(table),
    )
    service = ExportService(
        repository=repository,
        publisher=(
            MemoryExportPublisher(process_immediately=False)
            if publisher is None
            else publisher
        ),
        metrics=MetricsCollector(namespace="Tests"),
    )
    return service, table


async def _build_service_with_record(
    *,
    status: ExportStatus = ExportStatus.QUEUED,
) -> ExportService:
    repository = MemoryExportRepository()
    now = datetime.now(tz=UTC)
    await repository.create(
        ExportRecord(
            export_id="export-1",
            scope_id="scope-1",
            request_id="req-1",
            source_key="uploads/scope-1/source.csv",
            filename="source.csv",
            status=status,
            output=None,
            error=None,
            created_at=now,
            updated_at=now,
        )
    )
    return ExportService(
        repository=repository,
        publisher=MemoryExportPublisher(process_immediately=False),
        metrics=MetricsCollector(namespace="Tests"),
    )


@pytest.mark.anyio
async def test_create_and_cancel_export_tracks_execution_metadata() -> None:
    repository = MemoryExportRepository()
    publisher = _RecordingExportPublisher()
    service = ExportService(
        repository=repository,
        publisher=publisher,
        metrics=MetricsCollector(namespace="Tests"),
    )

    created = await service.create(
        source_key="uploads/scope-1/source.csv",
        filename="source.csv",
        scope_id="scope-1",
    )
    assert created.execution_arn == "arn:aws:states:::execution:test"
    assert created.cancel_requested_at is None

    cancelled = await service.cancel(
        export_id=created.export_id,
        scope_id="scope-1",
    )
    assert cancelled.status == ExportStatus.CANCELLED
    assert cancelled.cancel_requested_at is not None
    assert publisher.stop_calls == [
        {
            "execution_arn": "arn:aws:states:::execution:test",
            "cause": "export cancelled by caller",
        }
    ]


@pytest.mark.anyio
async def test_dynamo_export_service_immediate_get_is_strongly_consistent() -> (
    None
):
    service, table = _dynamo_export_service()

    created = await service.create(
        source_key="uploads/scope-1/source.csv",
        filename="source.csv",
        scope_id="scope-1",
    )
    fetched = await service.get(
        export_id=created.export_id,
        scope_id="scope-1",
    )

    assert fetched.export_id == created.export_id
    assert table.get_item_calls[-1]["ConsistentRead"] is True


@pytest.mark.anyio
async def test_dynamo_export_service_immediate_cancel_reads_strongly() -> None:
    publisher = _RecordingExportPublisher()
    service, table = _dynamo_export_service(publisher=publisher)

    created = await service.create(
        source_key="uploads/scope-1/source.csv",
        filename="source.csv",
        scope_id="scope-1",
    )
    cancelled = await service.cancel(
        export_id=created.export_id,
        scope_id="scope-1",
    )

    assert cancelled.status == ExportStatus.CANCELLED
    assert table.get_item_calls[-1]["ConsistentRead"] is True
    assert publisher.stop_calls == [
        {
            "execution_arn": "arn:aws:states:::execution:test",
            "cause": "export cancelled by caller",
        }
    ]


@pytest.mark.anyio
async def test_dynamo_export_status_updates_are_immediately_visible() -> None:
    service, table = _dynamo_export_service()

    created = await service.create(
        source_key="uploads/scope-1/source.csv",
        filename="source.csv",
        scope_id="scope-1",
    )
    updated = await service.update_status(
        export_id=created.export_id,
        status=ExportStatus.VALIDATING,
    )
    fetched = await service.get(
        export_id=created.export_id,
        scope_id="scope-1",
    )

    assert updated.status == ExportStatus.VALIDATING
    assert fetched.status == ExportStatus.VALIDATING
    assert table.get_item_calls[-1]["ConsistentRead"] is True


@pytest.mark.anyio
async def test_dynamo_export_list_remains_gsi_backed_and_eventual() -> None:
    service, table = _dynamo_export_service()

    await service.create(
        source_key="uploads/scope-1/source.csv",
        filename="source.csv",
        scope_id="scope-1",
    )
    listed = await service.list_for_scope(scope_id="scope-1")

    assert len(listed) == 1
    assert "ConsistentRead" not in table.query_calls[-1]


@pytest.mark.anyio
async def test_update_status_maps_missing_export_to_not_found() -> None:
    service = ExportService(
        repository=MemoryExportRepository(),
        publisher=MemoryExportPublisher(process_immediately=False),
        metrics=MetricsCollector(namespace="Tests"),
    )

    with pytest.raises(FileTransferError) as exc_info:
        await service.update_status(
            export_id="missing",
            status=ExportStatus.VALIDATING,
        )

    assert exc_info.value.code == "not_found"
    assert exc_info.value.message == "export not found"


@pytest.mark.anyio
async def test_update_status_maps_invalid_transition_to_conflict() -> None:
    service = await _build_service_with_record(status=ExportStatus.SUCCEEDED)

    with pytest.raises(FileTransferError) as exc_info:
        await service.update_status(
            export_id="export-1",
            status=ExportStatus.VALIDATING,
        )

    assert exc_info.value.code == "conflict"
    assert exc_info.value.message == "invalid export state transition"
    assert exc_info.value.details == {
        "export_id": "export-1",
        "current_status": "succeeded",
        "requested_status": "validating",
    }
