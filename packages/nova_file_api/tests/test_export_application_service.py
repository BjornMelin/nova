"""Unit tests for export application-layer request orchestration."""

from __future__ import annotations

from typing import Any

import pytest

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.application.exports import ExportApplicationService
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
