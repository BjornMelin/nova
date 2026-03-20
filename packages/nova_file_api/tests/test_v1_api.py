"""Tests for v1 FastAPI endpoints using TestClient and create_app."""

from __future__ import annotations

from fastapi.testclient import TestClient
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.config import Settings
from nova_file_api.jobs import (
    JobService,
    MemoryJobPublisher,
    MemoryJobRepository,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import (
    JobRecord,
    JobStatus,
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
)
from .support.doubles import StubAuthenticator, StubTransferService

AUTH_HEADERS = {"Authorization": "Bearer token-123"}


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


class _FailingListJobRepository:
    async def create(self, record: JobRecord) -> None:
        del record
        raise AssertionError("not expected in list-only test")

    async def get(self, job_id: str) -> JobRecord | None:
        del job_id
        return None

    async def update(self, record: JobRecord) -> None:
        del record

    async def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        del record, expected_status
        return False

    async def list_for_scope(
        self,
        *,
        scope_id: str,
        limit: int,
    ) -> list[JobRecord]:
        del scope_id, limit
        raise RuntimeError("jobs table is not configured for scoped listing")

    async def healthcheck(self) -> bool:
        return True


def _build_v1_deps(
    *,
    file_transfer_bucket: str = "test-transfer-bucket",
) -> RuntimeDeps:
    """Build an in-memory dependency set for v1 route tests."""
    settings = Settings.model_validate(
        {
            "jobs_enabled": True,
            "file_transfer_bucket": file_transfer_bucket,
        }
    )

    metrics = MetricsCollector(namespace="Tests")
    shared, cache = build_cache_stack()
    repository = MemoryJobRepository()
    job_service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    return build_runtime_deps(
        settings=settings,
        metrics=metrics,
        shared_cache=shared,
        cache=cache,
        authenticator=StubAuthenticator(),
        transfer_service=StubTransferService(),
        job_service=job_service,
        activity_store=MemoryActivityStore(),
        idempotency_enabled=True,
        use_in_memory_shared_cache=True,
    )


def test_v1_health_and_capabilities() -> None:
    """Verifies v1 live/ready health and capability keys are exposed."""
    app = build_test_app(_build_v1_deps(file_transfer_bucket=""))
    with TestClient(app) as client:
        live = client.get("/v1/health/live")
        ready = client.get("/v1/health/ready")
        caps = client.get("/v1/capabilities")

    assert live.status_code == 200
    assert live.json() == {"ok": True}
    assert ready.status_code == 503
    ready_payload = ready.json()
    assert ready_payload["ok"] is False
    assert ready_payload["checks"]["bucket_configured"] is False
    assert caps.status_code == 200
    cap_keys = {entry["key"] for entry in caps.json()["capabilities"]}
    assert {"jobs", "jobs.events.poll", "transfers"}.issubset(cap_keys)


def test_v1_upload_introspect_returns_uploaded_parts() -> None:
    """Verify multipart introspection is exposed on the canonical v1 route."""
    deps = _build_v1_deps()
    deps.transfer_service = _IntrospectTransferService()
    app = build_test_app(deps)
    with TestClient(app) as client:
        response = client.post(
            "/v1/transfers/uploads/introspect",
            headers=AUTH_HEADERS,
            json={
                "key": "uploads/scope-1/file.csv",
                "upload_id": "upload-1",
            },
        )

    assert response.status_code == 200
    assert response.json()["parts"] == [{"part_number": 1, "etag": '"etag-1"'}]


def test_v1_jobs_create_list_get_retry_and_events() -> None:
    """Verifies v1 job create/list/get/retry/event lifecycle behavior."""
    app = build_test_app(_build_v1_deps())
    with TestClient(app) as client:
        create_resp = client.post(
            "/v1/jobs",
            headers=AUTH_HEADERS,
            json={"job_type": "transform", "payload": {"input": "a"}},
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        job_id = created["job_id"]

        list_resp = client.get("/v1/jobs", headers=AUTH_HEADERS)
        assert list_resp.status_code == 200
        assert any(
            item["job_id"] == job_id for item in list_resp.json()["jobs"]
        )

        get_resp = client.get(
            f"/v1/jobs/{job_id}",
            headers=AUTH_HEADERS,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["job"]["job_id"] == job_id

        retry_resp = client.post(
            f"/v1/jobs/{job_id}/retry",
            headers=AUTH_HEADERS,
        )
        assert retry_resp.status_code == 409

        events_resp = client.get(
            f"/v1/jobs/{job_id}/events",
            headers=AUTH_HEADERS,
        )
        assert events_resp.status_code == 200
        events = events_resp.json()["events"]
        assert len(events) == 1
        assert events[0]["job_id"] == job_id


def test_v1_resource_plan_and_release_info() -> None:
    """Verifies v1 resource planning plus release metadata contract."""
    app = build_test_app(_build_v1_deps())
    with TestClient(app) as client:
        plan = client.post(
            "/v1/resources/plan", json={"resources": ["jobs", "unknown"]}
        )
        info = client.get("/v1/releases/info")

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


def test_v1_jobs_rejects_blank_idempotency_key() -> None:
    """Verifies v1 jobs reject blank Idempotency-Key header values."""
    app = build_test_app(_build_v1_deps())
    with TestClient(app) as client:
        resp = client.post(
            "/v1/jobs",
            headers={
                **AUTH_HEADERS,
                "Idempotency-Key": "",
            },
            json={"job_type": "transform", "payload": {"input": "a"}},
        )
        whitespace_resp = client.post(
            "/v1/jobs",
            headers={
                **AUTH_HEADERS,
                "Idempotency-Key": "   ",
            },
            json={"job_type": "transform", "payload": {"input": "a"}},
        )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_request"
    assert whitespace_resp.status_code == 422
    assert whitespace_resp.json()["error"]["code"] == "invalid_request"


def test_v1_jobs_list_scoped_config_error_returns_internal_error() -> None:
    """Verify a scoped jobs listing config error returns an internal error."""
    settings = Settings.model_validate(
        {
            "JOBS_ENABLED": True,
        }
    )

    metrics = MetricsCollector(namespace="Tests")
    shared, cache = build_cache_stack()
    repository = _FailingListJobRepository()
    job_service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    deps = build_runtime_deps(
        settings=settings,
        metrics=metrics,
        shared_cache=shared,
        cache=cache,
        authenticator=StubAuthenticator(),
        transfer_service=StubTransferService(),
        job_service=job_service,
        activity_store=MemoryActivityStore(),
        idempotency_enabled=False,
    )

    app = build_test_app(deps)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/v1/jobs",
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "internal_error"
    assert payload["error"]["message"] == "unexpected internal error"


def test_v1_jobs_rejects_legacy_session_scope_body_fields() -> None:
    """Public request models reject removed session-scope surrogate fields."""
    app = build_test_app(_build_v1_deps())
    with TestClient(app) as client:
        response = client.post(
            "/v1/jobs",
            headers=AUTH_HEADERS,
            json={
                "job_type": "transform",
                "payload": {"input": "a"},
                "session_id": "scope-v1",
            },
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "invalid_request"
