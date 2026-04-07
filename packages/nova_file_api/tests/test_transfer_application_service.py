"""Unit tests for transfer application-layer request orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.application.transfers import TransferApplicationService
from nova_file_api.idempotency import IdempotencyClaim, IdempotencyStore
from nova_file_api.models import (
    InitiateUploadRequest,
    InitiateUploadResponse,
    Principal,
    SignPartsRequest,
    SignPartsResponse,
)
from nova_file_api.transfer import TransferService
from nova_file_api.upload_sessions import UploadStrategy
from nova_runtime_support.metrics import MetricsCollector

from .support.doubles import StubTransferService


class _FakeIdempotencyStore(IdempotencyStore):
    def __init__(self) -> None:
        self.enabled = True
        self.replay: dict[str, Any] | None = None
        self.claim_result: IdempotencyClaim | None = IdempotencyClaim(
            cache_key="cache-key",
            owner_token="claim-owner",  # noqa: S106 - test token only
            request_hash="request-hash",
        )
        self.stored_payload: dict[str, Any] | None = None

    async def load_response(self, **_: Any) -> dict[str, Any] | None:
        return self.replay

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


class _RecordingTransferService(StubTransferService):
    def __init__(self) -> None:
        self.initiate_calls = 0
        self.sign_parts_calls = 0

    async def initiate_upload(
        self,
        request: InitiateUploadRequest,
        principal: Principal,
    ) -> InitiateUploadResponse:
        del request
        self.initiate_calls += 1
        return InitiateUploadResponse(
            strategy=UploadStrategy.SINGLE,
            bucket="bucket",
            key=f"uploads/{principal.scope_id}/file.csv",
            session_id="session-1",
            expires_in_seconds=900,
            policy_id="default",
            policy_version="2026-04-03",
            max_concurrency_hint=4,
            sign_batch_size_hint=64,
            accelerate_enabled=False,
            checksum_algorithm=None,
            checksum_mode="none",
            resumable_until=datetime.now(tz=UTC),
            url="https://example.com/upload",
        )

    async def sign_parts(
        self,
        request: SignPartsRequest,
        principal: Principal,
    ) -> SignPartsResponse:
        del request, principal
        self.sign_parts_calls += 1
        return SignPartsResponse(
            expires_in_seconds=900,
            urls={1: "https://example.com/part-1"},
        )


def _principal() -> Principal:
    return Principal(subject="user-1", scope_id="scope-1")


@pytest.mark.anyio
async def test_initiate_upload_moves_orchestration_below_routes() -> None:
    metrics = MetricsCollector(namespace="Tests")
    activity_store = MemoryActivityStore()
    idempotency_store = _FakeIdempotencyStore()
    transfer_service = _RecordingTransferService()
    service = TransferApplicationService(
        metrics=metrics,
        transfer_service=cast(TransferService, transfer_service),
        activity_store=activity_store,
        idempotency_store=idempotency_store,
    )

    response = await service.initiate_upload(
        payload=InitiateUploadRequest(
            filename="file.csv",
            size_bytes=1024,
        ),
        principal=_principal(),
        idempotency_key="idempotency-1",
    )

    assert response.session_id == "session-1"
    assert transfer_service.initiate_calls == 1
    assert idempotency_store.stored_payload is not None
    assert metrics.counters_snapshot()["uploads_initiate_total"] == 1
    assert "uploads_initiate_ms" in metrics.latency_snapshot()
    assert await activity_store.summary() == {
        "events_total": 1,
        "active_users_today": 1,
        "distinct_event_types": 1,
    }


@pytest.mark.anyio
async def test_sign_parts_records_success_outside_route_layer() -> None:
    metrics = MetricsCollector(namespace="Tests")
    activity_store = MemoryActivityStore()
    service = TransferApplicationService(
        metrics=metrics,
        transfer_service=cast(TransferService, _RecordingTransferService()),
        activity_store=activity_store,
        idempotency_store=_FakeIdempotencyStore(),
    )

    response = await service.sign_parts(
        payload=SignPartsRequest(
            key="uploads/scope-1/file.csv",
            upload_id="upload-1",
            part_numbers=[1],
        ),
        principal=_principal(),
    )

    assert response.urls[1] == "https://example.com/part-1"
    assert metrics.counters_snapshot()["uploads_sign_parts_total"] == 1
    assert "uploads_sign_parts_ms" in metrics.latency_snapshot()
    assert await activity_store.summary() == {
        "events_total": 1,
        "active_users_today": 1,
        "distinct_event_types": 1,
    }
