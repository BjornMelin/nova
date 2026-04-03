"""Tests for v1 FastAPI endpoints using the shared ASGI test harness."""

from __future__ import annotations

import pytest

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.config import Settings
from nova_file_api.exports import (
    ExportRepository,
    ExportService,
    MemoryExportPublisher,
    MemoryExportRepository,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import (
    ExportRecord,
    ExportStatus,
    Principal,
    UploadedPart,
    UploadIntrospectionRequest,
    UploadIntrospectionResponse,
)

from .support.app import (
    RuntimeDeps,
    build_cache_stack,
    build_runtime_deps,
    build_test_app,
    request_app,
)
from .support.doubles import StubAuthenticator, StubTransferService

AUTH_HEADERS = {"Authorization": "Bearer token-123"}
EXPORT_REQUEST: dict[str, object] = {
    "source_key": "uploads/scope-1/source.csv",
    "filename": "source.csv",
}


class _IntrospectTransferService(StubTransferService):
    async def introspect_upload(
        self,
        request: UploadIntrospectionRequest,
        principal: Principal,
    ) -> UploadIntrospectionResponse:
        del request, principal
        return UploadIntrospectionResponse(
            bucket="test-transfer-bucket",
            key="uploads/scope-1/file.csv",
            upload_id="upload-1",
            part_size_bytes=128 * 1024 * 1024,
            parts=[UploadedPart(part_number=1, etag='"etag-1"')],
        )


class _FailingListExportRepository:
    async def create(self, record: ExportRecord) -> None:
        del record
        raise AssertionError("not expected in list-only test")

    async def get(self, export_id: str) -> ExportRecord | None:
        del export_id
        return None

    async def update(self, record: ExportRecord) -> None:
        del record

    async def update_if_status(
        self,
        *,
        record: ExportRecord,
        expected_status: ExportStatus,
    ) -> bool:
        del record, expected_status
        return False

    async def list_for_scope(
        self,
        *,
        scope_id: str,
        limit: int,
    ) -> list[ExportRecord]:
        del scope_id, limit
        raise RuntimeError("exports table is not configured for scoped listing")

    async def healthcheck(self) -> bool:
        return True


def _build_v1_deps(
    *,
    file_transfer_bucket: str = "test-transfer-bucket",
    process_immediately: bool = True,
) -> RuntimeDeps:
    """Build an in-memory dependency set for v1 route tests."""
    settings = Settings.model_validate(
        {
            "exports_enabled": True,
            "file_transfer_bucket": file_transfer_bucket,
            "idempotency_dynamodb_table": "test-idempotency",
            "cors_allowed_origins": ["https://app.example.com"],
        }
    )

    metrics = MetricsCollector(namespace="Tests")
    cache = build_cache_stack()
    repository = MemoryExportRepository()
    export_service = ExportService(
        repository=repository,
        publisher=MemoryExportPublisher(
            process_immediately=process_immediately
        ),
        metrics=metrics,
    )
    return build_runtime_deps(
        settings=settings,
        metrics=metrics,
        cache=cache,
        authenticator=StubAuthenticator(),
        transfer_service=StubTransferService(),
        export_service=export_service,
        activity_store=MemoryActivityStore(),
        idempotency_enabled=True,
    )


@pytest.mark.anyio
async def test_v1_health_and_capabilities() -> None:
    """Verifies v1 live/ready health and capability keys are exposed."""
    app = build_test_app(_build_v1_deps(file_transfer_bucket=""))
    live = await request_app(app, "GET", "/v1/health/live")
    ready = await request_app(app, "GET", "/v1/health/ready")
    caps = await request_app(app, "GET", "/v1/capabilities")
    transfer_caps = await request_app(app, "GET", "/v1/capabilities/transfers")

    assert live.status_code == 200
    assert live.json() == {"ok": True}
    assert ready.status_code == 503
    ready_payload = ready.json()
    assert ready_payload["ok"] is False
    assert ready_payload["checks"]["bucket_configured"] is False
    assert ready_payload["checks"]["export_runtime"] is True
    assert ready_payload["checks"]["transfer_runtime"] is True
    assert caps.status_code == 200
    cap_payload = caps.json()["capabilities"]
    cap_keys = {entry["key"] for entry in cap_payload}
    assert {
        "exports",
        "exports.status.poll",
        "transfers",
        "transfers.policy",
    }.issubset(cap_keys)
    policy_capability = next(
        entry for entry in cap_payload if entry["key"] == "transfers.policy"
    )
    assert policy_capability["details"]["policy_id"] == "default"
    assert transfer_caps.status_code == 200
    transfer_policy = transfer_caps.json()
    assert transfer_policy["policy_id"] == "default"
    assert transfer_policy["sign_batch_size_hint"] >= 32


@pytest.mark.anyio
async def test_v1_upload_introspect_returns_uploaded_parts() -> None:
    """Verify multipart introspection is exposed on the canonical v1 route."""
    deps = _build_v1_deps()
    deps.transfer_service = _IntrospectTransferService()
    app = build_test_app(deps)
    response = await request_app(
        app,
        "POST",
        "/v1/transfers/uploads/introspect",
        headers=AUTH_HEADERS,
        json={
            "key": "uploads/scope-1/file.csv",
            "upload_id": "upload-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["parts"] == [{"part_number": 1, "etag": '"etag-1"'}]


@pytest.mark.anyio
async def test_v1_exports_create_list_and_get() -> None:
    """Verify the explicit export workflow resource lifecycle."""
    app = build_test_app(_build_v1_deps())
    create_resp = await request_app(
        app,
        "POST",
        "/v1/exports",
        headers=AUTH_HEADERS,
        json=EXPORT_REQUEST,
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    export_id = created["export_id"]
    assert created["status"] == "succeeded"

    list_resp = await request_app(
        app,
        "GET",
        "/v1/exports",
        headers=AUTH_HEADERS,
    )
    assert list_resp.status_code == 200
    assert any(
        item["export_id"] == export_id for item in list_resp.json()["exports"]
    )

    get_resp = await request_app(
        app,
        "GET",
        f"/v1/exports/{export_id}",
        headers=AUTH_HEADERS,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["export_id"] == export_id


@pytest.mark.anyio
async def test_v1_exports_cancel_non_terminal_resource() -> None:
    """Verify canceling a queued export returns the cancelled resource."""
    app = build_test_app(_build_v1_deps(process_immediately=False))
    create_resp = await request_app(
        app,
        "POST",
        "/v1/exports",
        headers=AUTH_HEADERS,
        json=EXPORT_REQUEST,
    )
    export_id = create_resp.json()["export_id"]

    cancel_resp = await request_app(
        app,
        "POST",
        f"/v1/exports/{export_id}/cancel",
        headers=AUTH_HEADERS,
    )

    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


@pytest.mark.anyio
async def test_v1_resource_plan_and_release_info() -> None:
    """Verifies v1 resource planning plus release metadata contract."""
    app = build_test_app(_build_v1_deps())
    plan = await request_app(
        app,
        "POST",
        "/v1/resources/plan",
        json={"resources": ["exports", "unknown"]},
    )
    info = await request_app(app, "GET", "/v1/releases/info")

    assert plan.status_code == 200
    payload = plan.json()
    assert len(payload["plan"]) == 2
    unknown = next(i for i in payload["plan"] if i["resource"] == "unknown")
    assert unknown["supported"] is False
    assert unknown["reason"] == "unsupported_resource"

    assert info.status_code == 200
    release = info.json()
    assert release["name"]
    assert release["version"]
    assert isinstance(release["environment"], str)
    assert release["environment"]


@pytest.mark.anyio
async def test_v1_release_info_includes_cors_header_for_allowed_origin() -> (
    None
):
    """Release info should emit the configured browser origin header."""
    app = build_test_app(_build_v1_deps())

    response = await request_app(
        app,
        "GET",
        "/v1/releases/info",
        headers={"Origin": "https://app.example.com"},
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://app.example.com"
    )


@pytest.mark.anyio
async def test_v1_release_info_disallowed_origin_no_cors_header() -> None:
    """Release info should not expose CORS origin for an untrusted domain."""
    app = build_test_app(_build_v1_deps())

    response = await request_app(
        app,
        "GET",
        "/v1/releases/info",
        headers={"Origin": "https://evil.example.com"},
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in (None, "null")


@pytest.mark.anyio
async def test_v1_exports_reject_blank_idempotency_key() -> None:
    """Verifies v1 exports reject blank Idempotency-Key header values."""
    app = build_test_app(_build_v1_deps())
    resp = await request_app(
        app,
        "POST",
        "/v1/exports",
        headers={**AUTH_HEADERS, "Idempotency-Key": ""},
        json=EXPORT_REQUEST,
    )
    whitespace_resp = await request_app(
        app,
        "POST",
        "/v1/exports",
        headers={**AUTH_HEADERS, "Idempotency-Key": "   "},
        json=EXPORT_REQUEST,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_request"
    assert whitespace_resp.status_code == 422
    assert whitespace_resp.json()["error"]["code"] == "invalid_request"


@pytest.mark.anyio
async def test_v1_exports_list_scoped_config_error_returns_internal_error() -> (
    None
):
    """Verify a scoped export listing config error returns an internal error."""
    settings = Settings.model_validate(
        {
            "exports_enabled": True,
            "idempotency_dynamodb_table": "test-idempotency",
        }
    )
    metrics = MetricsCollector(namespace="Tests")
    cache = build_cache_stack()
    repository: ExportRepository = _FailingListExportRepository()
    export_service = ExportService(
        repository=repository,
        publisher=MemoryExportPublisher(),
        metrics=metrics,
    )
    deps = build_runtime_deps(
        settings=settings,
        metrics=metrics,
        cache=cache,
        authenticator=StubAuthenticator(),
        transfer_service=StubTransferService(),
        export_service=export_service,
        activity_store=MemoryActivityStore(),
        idempotency_enabled=False,
        export_repository=repository,
    )

    app = build_test_app(deps)
    response = await request_app(
        app,
        "GET",
        "/v1/exports",
        headers={**AUTH_HEADERS, "X-Request-Id": "req-v1-500"},
        raise_app_exceptions=False,
    )

    assert response.status_code == 500
    assert response.headers["X-Request-Id"] == "req-v1-500"
    payload = response.json()
    assert payload["error"]["code"] == "internal_error"
    assert payload["error"]["message"] == "unexpected internal error"
    assert payload["error"]["request_id"] == "req-v1-500"


@pytest.mark.anyio
async def test_v1_exports_reject_legacy_session_scope_body_fields() -> None:
    """Public request models reject removed legacy auth-surrogate fields."""
    app = build_test_app(_build_v1_deps())
    legacy_field = "_".join(("session", "id"))
    response = await request_app(
        app,
        "POST",
        "/v1/exports",
        headers=AUTH_HEADERS,
        json={
            "source_key": "uploads/scope-1/source.csv",
            "filename": "source.csv",
            legacy_field: "scope-v1",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "invalid_request"
