from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from botocore.exceptions import ClientError

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.errors import queue_unavailable
from nova_file_api.idempotency import (
    IdempotencyStore,
    idempotency_request_payload_hash,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import (
    ExportRecord,
    ExportStatus,
    InitiateUploadResponse,
    Principal,
    UploadStrategy,
)

from .support.app import (
    build_cache_stack,
    build_runtime_deps,
    build_test_app,
    request_app,
)
from .support.dynamodb import MemoryDynamoResource, MemoryDynamoTable

EXPORT_REQUEST: dict[str, object] = {
    "source_key": "uploads/scope-1/source.csv",
    "filename": "source.csv",
}
EXPORT_REQUEST_ALT_A: dict[str, object] = {
    "source_key": "uploads/scope-1/source-a.csv",
    "filename": "source.csv",
}


class _StubAuthenticator:
    async def authenticate(
        self,
        *,
        token: str | None,
    ) -> Principal:
        del token
        return Principal(
            subject="user-1",
            scope_id="scope-1",
            tenant_id=None,
            scopes=(),
            permissions=("metrics:read",),
        )


class _StubExportService:
    calls: int

    def __init__(self) -> None:
        self.calls = 0

    async def create(
        self,
        *,
        source_key: str,
        filename: str,
        scope_id: str,
        request_id: str | None = None,
    ) -> ExportRecord:
        self.calls += 1
        now = datetime.now(tz=UTC)
        return ExportRecord(
            export_id=f"export-{self.calls}",
            scope_id=scope_id,
            request_id=request_id,
            source_key=source_key,
            filename=filename,
            status=ExportStatus.QUEUED,
            output=None,
            error=None,
            created_at=now,
            updated_at=now,
        )

    async def get(self, *, export_id: str, scope_id: str) -> ExportRecord:
        del export_id, scope_id
        raise RuntimeError("not used by this test")

    async def cancel(self, *, export_id: str, scope_id: str) -> ExportRecord:
        del export_id, scope_id
        raise RuntimeError("not used by this test")


class _FailFirstCreateExportService(_StubExportService):
    async def create(
        self,
        *,
        source_key: str,
        filename: str,
        scope_id: str,
        request_id: str | None = None,
    ) -> ExportRecord:
        if self.calls == 0:
            self.calls += 1
            raise queue_unavailable(
                "export create failed because queue unavailable"
            )
        return await super().create(
            source_key=source_key,
            filename=filename,
            scope_id=scope_id,
            request_id=request_id,
        )


class _StubTransferService:
    calls: int

    def __init__(self) -> None:
        self.calls = 0

    async def initiate_upload(
        self,
        payload: object,
        principal: Principal,
    ) -> InitiateUploadResponse:
        del payload, principal
        self.calls += 1
        return InitiateUploadResponse(
            strategy=UploadStrategy.SINGLE,
            bucket="bucket-a",
            key=f"uploads/scope-1/object-{self.calls}",
            expires_in_seconds=900,
            url=f"https://example.local/upload/{self.calls}",
        )


class _FailCommitTable(MemoryDynamoTable):
    async def update_item(self, **kwargs: object) -> dict[str, object]:
        raise ClientError(
            error_response={
                "Error": {
                    "Code": "ProvisionedThroughputExceededException",
                    "Message": "simulated commit outage",
                }
            },
            operation_name="UpdateItem",
        )


def _idempotency_store(
    *,
    resource: MemoryDynamoResource | None = None,
    ttl_seconds: int = 300,
    clock: Any = None,
) -> IdempotencyStore:
    resource = MemoryDynamoResource() if resource is None else resource
    return IdempotencyStore(
        table_name="test-idempotency",
        dynamodb_resource=resource,
        enabled=True,
        ttl_seconds=ttl_seconds,
        key_prefix="nova",
        key_schema_version=1,
        _clock=(clock if clock is not None else (lambda: 1_000.0)),
    )


@pytest.mark.anyio
async def test_memory_dynamo_table_rejects_unknown_condition_expression() -> (
    None
):
    table = MemoryDynamoTable()

    with pytest.raises(ValueError, match="unsupported ConditionExpression"):
        await table.put_item(
            Item={"idempotency_key": "claim-1"},
            ConditionExpression="attribute_exists(idempotency_key)",
        )


@pytest.mark.anyio
async def test_v1_initiate_replays_response_for_same_idempotency_key() -> None:
    transfer_service = _StubTransferService()
    app = build_test_app(
        build_runtime_deps(
            settings=None,
            metrics=MetricsCollector(namespace="Tests"),
            cache=build_cache_stack(),
            authenticator=_StubAuthenticator(),
            transfer_service=transfer_service,
            export_service=_StubExportService(),
            activity_store=MemoryActivityStore(),
            idempotency_enabled=True,
        )
    )

    headers = {
        "Authorization": "Bearer token-123",
        "Idempotency-Key": "initiate-1",
    }
    first = await request_app(
        app,
        "POST",
        "/v1/transfers/uploads/initiate",
        headers=headers,
        json={
            "filename": "source.csv",
            "content_type": "text/csv",
            "size_bytes": 1,
        },
    )
    second = await request_app(
        app,
        "POST",
        "/v1/transfers/uploads/initiate",
        headers=headers,
        json={
            "filename": "source.csv",
            "content_type": "text/csv",
            "size_bytes": 1,
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert transfer_service.calls == 1


@pytest.mark.anyio
async def test_v1_exports_conflict_when_same_key_reused_for_other_payload() -> (
    None
):
    app = build_test_app(
        build_runtime_deps(
            settings=None,
            metrics=MetricsCollector(namespace="Tests"),
            cache=build_cache_stack(),
            authenticator=_StubAuthenticator(),
            transfer_service=_StubTransferService(),
            export_service=_StubExportService(),
            activity_store=MemoryActivityStore(),
            idempotency_enabled=True,
        )
    )

    headers = {
        "Authorization": "Bearer token-123",
        "Idempotency-Key": "export-1",
    }
    first = await request_app(
        app,
        "POST",
        "/v1/exports",
        headers=headers,
        json=EXPORT_REQUEST,
    )
    second = await request_app(
        app,
        "POST",
        "/v1/exports",
        headers=headers,
        json=EXPORT_REQUEST_ALT_A,
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"


@pytest.mark.anyio
async def test_v1_exports_failed_create_is_not_idempotency_replayed() -> None:
    export_service = _FailFirstCreateExportService()
    app = build_test_app(
        build_runtime_deps(
            settings=None,
            metrics=MetricsCollector(namespace="Tests"),
            cache=build_cache_stack(),
            authenticator=_StubAuthenticator(),
            transfer_service=_StubTransferService(),
            export_service=export_service,
            activity_store=MemoryActivityStore(),
            idempotency_enabled=True,
        )
    )

    headers = {
        "Authorization": "Bearer token-123",
        "Idempotency-Key": "export-retry",
    }
    first = await request_app(
        app,
        "POST",
        "/v1/exports",
        headers=headers,
        json=EXPORT_REQUEST,
    )
    second = await request_app(
        app,
        "POST",
        "/v1/exports",
        headers=headers,
        json=EXPORT_REQUEST,
    )

    assert first.status_code == 503
    assert first.json()["error"]["code"] == "queue_unavailable"
    assert second.status_code == 201
    assert export_service.calls == 2


@pytest.mark.anyio
async def test_v1_initiate_store_failure_preserves_claim_for_safe_retry() -> (
    None
):
    resource = MemoryDynamoResource(
        tables={"test-idempotency": _FailCommitTable()}
    )
    app = build_test_app(
        build_runtime_deps(
            settings=None,
            metrics=MetricsCollector(namespace="Tests"),
            cache=build_cache_stack(),
            authenticator=_StubAuthenticator(),
            transfer_service=_StubTransferService(),
            export_service=_StubExportService(),
            activity_store=MemoryActivityStore(),
            idempotency_enabled=True,
            dynamodb_resource=resource,
        )
    )

    headers = {
        "Authorization": "Bearer token-123",
        "Idempotency-Key": "initiate-store-failure",
    }
    payload: dict[str, object] = {
        "filename": "source.csv",
        "content_type": "text/csv",
        "size_bytes": 1,
    }
    first = await request_app(
        app,
        "POST",
        "/v1/transfers/uploads/initiate",
        headers=headers,
        json=payload,
    )
    second = await request_app(
        app,
        "POST",
        "/v1/transfers/uploads/initiate",
        headers=headers,
        json=payload,
    )

    assert first.status_code == 503
    assert first.json()["error"]["code"] == "idempotency_unavailable"
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"


@pytest.mark.anyio
async def test_shared_idempotency_store_prevents_duplicate_claims() -> None:
    resource = MemoryDynamoResource()
    first_store = _idempotency_store(resource=resource)
    second_store = _idempotency_store(resource=resource)

    first_claim = await first_store.claim_request(
        route="/v1/exports",
        scope_id="scope-1",
        idempotency_key="shared-claim",
        request_payload=EXPORT_REQUEST,
    )

    assert first_claim is not None
    with pytest.raises(Exception, match="already in progress"):
        _ = await second_store.claim_request(
            route="/v1/exports",
            scope_id="scope-1",
            idempotency_key="shared-claim",
            request_payload=EXPORT_REQUEST,
        )


@pytest.mark.anyio
async def test_expired_items_are_filtered_before_replay() -> None:
    resource = MemoryDynamoResource()
    store = _idempotency_store(resource=resource, clock=lambda: 1_000.0)
    table = resource.Table("test-idempotency")
    response_key = store._entry_cache_key(
        route="/v1/exports",
        scope_id="scope-1",
        idempotency_key="expired-entry",
    )
    table.put_raw(
        response_key,
        {
            "idempotency_key": response_key,
            "state": "committed",
            "request_hash": idempotency_request_payload_hash(
                payload=EXPORT_REQUEST
            ),
            "owner_token": "owner-1",
            "response": {"export_id": "stale"},
            "expires_at": 999,
        },
    )

    response = await store.load_response(
        route="/v1/exports",
        scope_id="scope-1",
        idempotency_key="expired-entry",
        request_payload=EXPORT_REQUEST,
    )
    assert response is None


@pytest.mark.anyio
async def test_expired_claim_can_be_reclaimed() -> None:
    resource = MemoryDynamoResource()
    store = _idempotency_store(resource=resource, clock=lambda: 1_000.0)
    table = resource.Table("test-idempotency")
    claim_key = store._entry_cache_key(
        route="/v1/exports",
        scope_id="scope-1",
        idempotency_key="expired-claim",
    )
    table.put_raw(
        claim_key,
        {
            "idempotency_key": claim_key,
            "state": "in_progress",
            "request_hash": idempotency_request_payload_hash(
                payload=EXPORT_REQUEST
            ),
            "owner_token": "owner-old",
            "expires_at": 999,
        },
    )

    claim = await store.claim_request(
        route="/v1/exports",
        scope_id="scope-1",
        idempotency_key="expired-claim",
        request_payload=EXPORT_REQUEST,
    )

    assert claim is not None
    current = table.get_raw(claim_key)
    assert current is not None
    assert current["owner_token"] == claim.owner_token


@pytest.mark.anyio
async def test_discard_claim_keeps_newer_owner_when_claim_was_replaced() -> (
    None
):
    resource = MemoryDynamoResource()
    store = _idempotency_store(resource=resource, clock=lambda: 1_000.0)
    claim = await store.claim_request(
        route="/v1/exports",
        scope_id="scope-1",
        idempotency_key="replaced-claim",
        request_payload=EXPORT_REQUEST,
    )
    assert claim is not None

    table = resource.Table("test-idempotency")
    new_owner_token = "-".join(("replacement", "owner"))
    table.put_raw(
        claim.cache_key,
        {
            "idempotency_key": claim.cache_key,
            "state": "in_progress",
            "request_hash": claim.request_hash,
            "owner_token": new_owner_token,
            "expires_at": 1_500,
        },
    )

    await store.discard_claim(claim=claim)

    remaining = table.get_raw(claim.cache_key)
    assert remaining is not None
    assert remaining["owner_token"] == new_owner_token
