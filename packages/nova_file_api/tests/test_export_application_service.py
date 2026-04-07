"""Unit tests for export application-layer request orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from nova_file_api.activity import ActivityStore, MemoryActivityStore
from nova_file_api.application.exports import ExportApplicationService
from nova_file_api.export_models import ExportRecord, ExportStatus
from nova_file_api.exports import (
    ExportService,
    MemoryExportPublisher,
    MemoryExportRepository,
)
from nova_file_api.idempotency import IdempotencyClaim, IdempotencyStore
from nova_file_api.models import CreateExportRequest, Principal
from nova_runtime_support.metrics import MetricsCollector


class _FakeIdempotencyStore(IdempotencyStore):
    def __init__(self) -> None:
        self.enabled = True
        self.claim_result = IdempotencyClaim(
            cache_key="cache-key",
            owner_token="claim-owner",  # noqa: S106 - test token only
            request_hash="request-hash",
        )
        self.stored_payload: dict[str, Any] | None = None

    async def load_response(self, **_: Any) -> dict[str, Any] | None:
        return None

    async def claim_request(self, **_: Any) -> IdempotencyClaim | None:
        return self.claim_result

    async def store_response(
        self,
        *,
        claim: IdempotencyClaim,
        response_payload: dict[str, Any],
    ) -> None:
        assert claim == self.claim_result
        self.stored_payload = response_payload

    async def discard_claim(self, **_: Any) -> None:
        return None


def _export_record(
    *,
    export_id: str = "export-1",
    scope_id: str = "scope-1",
    status: ExportStatus = ExportStatus.QUEUED,
    cancel_requested_at: datetime | None = None,
) -> ExportRecord:
    now = datetime.now(tz=UTC)
    return ExportRecord(
        export_id=export_id,
        scope_id=scope_id,
        request_id="req-1",
        source_key="uploads/scope-1/source.csv",
        filename="source.csv",
        status=status,
        output=None,
        error=None,
        execution_arn=None,
        cancel_requested_at=cancel_requested_at,
        source_size_bytes=None,
        copy_strategy=None,
        copy_export_key=None,
        copy_upload_id=None,
        copy_part_size_bytes=None,
        copy_part_count=None,
        copying_entered_at=None,
        finalizing_entered_at=None,
        created_at=now,
        updated_at=now,
    )


class _RecordingActivityStore:
    def __init__(self) -> None:
        self.records: list[tuple[str, str | None]] = []

    async def record(
        self,
        *,
        principal: Principal,
        event_type: str,
        details: str | None = None,
    ) -> None:
        del principal
        self.records.append((event_type, details))

    async def summary(self) -> dict[str, int]:
        return {
            "events_total": len(self.records),
            "active_users_today": 1 if self.records else 0,
            "distinct_event_types": len(
                {event_type for event_type, _ in self.records}
            ),
        }

    async def healthcheck(self) -> bool:
        return True


class _RecordingExportService:
    def __init__(self) -> None:
        self.get_calls: list[tuple[str, str]] = []
        self.list_calls: list[tuple[str, int]] = []
        self.cancel_calls: list[tuple[str, str]] = []
        self.get_record = _export_record()
        self.list_records = [
            _export_record(),
            _export_record(export_id="export-2", status=ExportStatus.SUCCEEDED),
        ]

    async def get(self, *, export_id: str, scope_id: str) -> ExportRecord:
        self.get_calls.append((export_id, scope_id))
        return self.get_record.model_copy(
            update={
                "export_id": export_id,
                "scope_id": scope_id,
            }
        )

    async def list_for_scope(
        self,
        *,
        scope_id: str,
        limit: int,
    ) -> list[ExportRecord]:
        self.list_calls.append((scope_id, limit))
        return [
            record.model_copy(update={"scope_id": scope_id})
            for record in self.list_records[:limit]
        ]

    async def cancel(self, *, export_id: str, scope_id: str) -> ExportRecord:
        self.cancel_calls.append((export_id, scope_id))
        now = datetime.now(tz=UTC)
        return self.get_record.model_copy(
            update={
                "export_id": export_id,
                "scope_id": scope_id,
                "status": ExportStatus.CANCELLED,
                "cancel_requested_at": now,
                "updated_at": now,
            }
        )


def _principal() -> Principal:
    return Principal(subject="user-1", scope_id="scope-1")


@pytest.mark.anyio
async def test_create_export_moves_mutation_orchestration_below_routes() -> (
    None
):
    metrics = MetricsCollector(namespace="Tests")
    activity_store = MemoryActivityStore()
    idempotency_store = _FakeIdempotencyStore()
    export_service = ExportService(
        repository=MemoryExportRepository(),
        publisher=MemoryExportPublisher(),
        metrics=metrics,
    )
    service = ExportApplicationService(
        metrics=metrics,
        export_service=export_service,
        activity_store=activity_store,
        idempotency_store=idempotency_store,
    )

    response = await service.create_export(
        payload=CreateExportRequest(
            source_key="uploads/scope-1/source.csv",
            filename="source.csv",
        ),
        principal=_principal(),
        request_id="req-1",
        idempotency_key="idempotency-1",
    )

    assert response.export_id
    assert idempotency_store.stored_payload is not None
    counters = metrics.counters_snapshot()
    assert counters["exports_create_total"] == 1
    assert counters["exports_created"] == 1
    assert "exports_create_ms" in metrics.latency_snapshot()
    assert await activity_store.summary() == {
        "events_total": 1,
        "active_users_today": 1,
        "distinct_event_types": 1,
    }


@pytest.mark.anyio
async def test_get_export_moves_read_orchestration_below_routes() -> None:
    metrics = MetricsCollector(namespace="Tests")
    activity_store = _RecordingActivityStore()
    export_service = _RecordingExportService()
    service = ExportApplicationService(
        metrics=metrics,
        export_service=cast(ExportService, export_service),
        activity_store=cast(ActivityStore, activity_store),
        idempotency_store=_FakeIdempotencyStore(),
    )

    response = await service.get_export(
        export_id="export-1",
        principal=_principal(),
    )

    assert response.export_id == "export-1"
    assert response.status == ExportStatus.QUEUED
    assert export_service.get_calls == [("export-1", "scope-1")]
    assert metrics.counters_snapshot()["exports_get_total"] == 1
    assert activity_store.records == []
    assert await activity_store.summary() == {
        "events_total": 0,
        "active_users_today": 0,
        "distinct_event_types": 0,
    }


@pytest.mark.anyio
async def test_list_exports_moves_query_orchestration_below_routes() -> None:
    metrics = MetricsCollector(namespace="Tests")
    activity_store = _RecordingActivityStore()
    export_service = _RecordingExportService()
    service = ExportApplicationService(
        metrics=metrics,
        export_service=cast(ExportService, export_service),
        activity_store=cast(ActivityStore, activity_store),
        idempotency_store=_FakeIdempotencyStore(),
    )

    response = await service.list_exports(scope_id="scope-1", limit=2)

    assert [export.export_id for export in response.exports] == [
        "export-1",
        "export-2",
    ]
    assert export_service.list_calls == [("scope-1", 2)]
    assert metrics.counters_snapshot() == {}
    assert activity_store.records == []
    assert await activity_store.summary() == {
        "events_total": 0,
        "active_users_today": 0,
        "distinct_event_types": 0,
    }


@pytest.mark.anyio
async def test_cancel_export_moves_mutation_orchestration_below_routes() -> (
    None
):
    metrics = MetricsCollector(namespace="Tests")
    activity_store = _RecordingActivityStore()
    export_service = _RecordingExportService()
    service = ExportApplicationService(
        metrics=metrics,
        export_service=cast(ExportService, export_service),
        activity_store=cast(ActivityStore, activity_store),
        idempotency_store=_FakeIdempotencyStore(),
    )

    response = await service.cancel_export(
        export_id="export-1",
        principal=_principal(),
    )

    assert response.export_id == "export-1"
    assert response.status == ExportStatus.CANCELLED
    assert response.cancel_requested_at is not None
    assert export_service.cancel_calls == [("export-1", "scope-1")]
    assert metrics.counters_snapshot()["exports_cancel_total"] == 1
    assert activity_store.records == [
        (
            "exports_cancel_success",
            "export_id=export-1 status=cancelled",
        )
    ]
    assert await activity_store.summary() == {
        "events_total": 1,
        "active_users_today": 1,
        "distinct_event_types": 1,
    }
