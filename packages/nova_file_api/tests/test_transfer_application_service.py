"""Unit tests for transfer application-layer request orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.application.transfers import TransferApplicationService
from nova_file_api.idempotency import IdempotencyClaim, IdempotencyStore
from nova_file_api.models import (
    AbortUploadRequest,
    AbortUploadResponse,
    CompletedPart,
    CompleteUploadRequest,
    CompleteUploadResponse,
    InitiateUploadRequest,
    InitiateUploadResponse,
    PresignDownloadRequest,
    PresignDownloadResponse,
    Principal,
    SignPartsRequest,
    SignPartsResponse,
    UploadedPart,
    UploadIntrospectionRequest,
    UploadIntrospectionResponse,
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
        self.introspect_calls = 0
        self.complete_calls = 0
        self.abort_calls = 0
        self.presign_download_calls = 0

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

    async def introspect_upload(
        self,
        request: UploadIntrospectionRequest,
        principal: Principal,
    ) -> UploadIntrospectionResponse:
        del principal
        self.introspect_calls += 1
        return UploadIntrospectionResponse(
            bucket="bucket",
            key=request.key,
            upload_id=request.upload_id,
            part_size_bytes=128,
            parts=[UploadedPart(part_number=1, etag="etag-1")],
        )

    async def complete_upload(
        self,
        request: CompleteUploadRequest,
        principal: Principal,
    ) -> CompleteUploadResponse:
        del request, principal
        self.complete_calls += 1
        return CompleteUploadResponse(
            bucket="bucket",
            key="uploads/scope-1/file.csv",
            etag="etag-1",
            version_id="version-1",
        )

    async def abort_upload(
        self,
        request: AbortUploadRequest,
        principal: Principal,
    ) -> AbortUploadResponse:
        del request, principal
        self.abort_calls += 1
        return AbortUploadResponse(ok=True)

    async def presign_download(
        self,
        request: PresignDownloadRequest,
        principal: Principal,
    ) -> PresignDownloadResponse:
        del request, principal
        self.presign_download_calls += 1
        return PresignDownloadResponse(
            bucket="bucket",
            key="uploads/scope-1/file.csv",
            url="https://example.com/download",
            expires_in_seconds=900,
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
    activity_store = _RecordingActivityStore()
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
    assert activity_store.records == [("uploads_sign_parts", None)]
    assert await activity_store.summary() == {
        "events_total": 1,
        "active_users_today": 1,
        "distinct_event_types": 1,
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    (
        "method_name",
        "payload",
        "call_attr",
        "expected_counter",
        "expected_metric",
        "expected_event_type",
        "expected_response_field",
        "expected_response_value",
    ),
    [
        (
            "introspect_upload",
            UploadIntrospectionRequest(
                key="uploads/scope-1/file.csv",
                upload_id="upload-1",
            ),
            "introspect_calls",
            "uploads_introspect_total",
            "uploads_introspect_ms",
            "uploads_introspect",
            "bucket",
            "bucket",
        ),
        (
            "complete_upload",
            CompleteUploadRequest(
                key="uploads/scope-1/file.csv",
                upload_id="upload-1",
                parts=[
                    CompletedPart(
                        part_number=1,
                        etag="etag-1",
                    )
                ],
            ),
            "complete_calls",
            "uploads_complete_total",
            "uploads_complete_ms",
            "uploads_complete",
            "etag",
            "etag-1",
        ),
        (
            "abort_upload",
            AbortUploadRequest(
                key="uploads/scope-1/file.csv",
                upload_id="upload-1",
            ),
            "abort_calls",
            "uploads_abort_total",
            "uploads_abort_ms",
            "uploads_abort",
            "ok",
            True,
        ),
        (
            "presign_download",
            PresignDownloadRequest(
                key="uploads/scope-1/file.csv",
                filename="file.csv",
            ),
            "presign_download_calls",
            "downloads_presign_total",
            "downloads_presign_ms",
            "downloads_presign",
            "url",
            "https://example.com/download",
        ),
    ],
)
async def test_remaining_transfer_methods_record_success_metrics_and_activity(
    method_name: str,
    payload: Any,
    call_attr: str,
    expected_counter: str,
    expected_metric: str,
    expected_event_type: str,
    expected_response_field: str,
    expected_response_value: Any,
) -> None:
    metrics = MetricsCollector(namespace="Tests")
    activity_store = _RecordingActivityStore()
    transfer_service = _RecordingTransferService()
    service = TransferApplicationService(
        metrics=metrics,
        transfer_service=cast(TransferService, transfer_service),
        activity_store=activity_store,
        idempotency_store=_FakeIdempotencyStore(),
    )

    response = await getattr(service, method_name)(
        payload=payload,
        principal=_principal(),
    )

    assert getattr(transfer_service, call_attr) == 1
    assert getattr(response, expected_response_field) == expected_response_value
    assert metrics.counters_snapshot()[expected_counter] == 1
    assert expected_metric in metrics.latency_snapshot()
    assert activity_store.records == [(expected_event_type, None)]
