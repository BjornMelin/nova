"""Tests for v1 FastAPI endpoints using TestClient and create_app."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.app import create_app
from nova_file_api.auth import Authenticator
from nova_file_api.cache import LocalTTLCache, SharedRedisCache, TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.container import AppContainer
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.jobs import (
    JobService,
    MemoryJobPublisher,
    MemoryJobRepository,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import AuthMode, JobRecord, JobStatus

from ._test_doubles import StubTransferService


class _FailingListJobRepository:
    async def create(self, record: JobRecord) -> None:
        """
        Reject creation requests for use in list-only tests by always raising an AssertionError.
        
        Parameters:
            record (JobRecord): Ignored input; present to match repository create signature.
        
        Raises:
            AssertionError: Always raised with message "not expected in list-only test".
        """
        del record
        raise AssertionError("not expected in list-only test")

    async def get(self, job_id: str) -> JobRecord | None:
        """
        Retrieve the job record for the given job ID; this failing repository never returns a record.
        
        Returns:
            None: Always returns None to simulate a missing or unavailable job.
        """
        del job_id
        return None

    async def update(self, record: JobRecord) -> None:
        """
        A no-op update method for tests that discards the provided JobRecord without performing any action.
        
        Parameters:
            record (JobRecord): The job record to update; this implementation ignores the value.
        """
        del record

    async def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        """
        Attempt to perform a conditional status update for a job record; this implementation always fails.
        
        Parameters:
            record (JobRecord): The job record proposed for update.
            expected_status (JobStatus): The status value required for the update to proceed.
        
        Returns:
            bool: `True` if the record was updated, `False` otherwise. This implementation always returns `False`.
        """
        del record, expected_status
        return False

    async def list_for_scope(
        self,
        *,
        scope_id: str,
        limit: int,
    ) -> list[JobRecord]:
        """
        Signal that scoped job listing is unsupported by this repository by raising a RuntimeError.
        
        Raises:
            RuntimeError: "jobs table is not configured for scoped listing"
        """
        del scope_id, limit
        raise RuntimeError("jobs table is not configured for scoped listing")


def _build_v1_container(
    *,
    file_transfer_bucket: str = "test-transfer-bucket",
) -> AppContainer:
    """
    Create an AppContainer preconfigured for v1 route tests.
    
    Parameters:
        file_transfer_bucket (str): Name of the file transfer bucket to set on the container's settings (defaults to "test-transfer-bucket").
    
    Returns:
        AppContainer: An in-memory container configured with test-oriented components:
            settings (auth same-origin, jobs enabled, provided file transfer bucket),
            MetricsCollector, TwoTierCache backed by a SharedRedisCache and LocalTTLCache,
            MemoryJobRepository and JobService with a MemoryJobPublisher,
            Authenticator, StubTransferService, MemoryActivityStore, and an IdempotencyStore enabled with a 300s TTL.
    """
    settings = Settings()
    settings.auth_mode = AuthMode.SAME_ORIGIN
    settings.jobs_enabled = True
    settings.file_transfer_bucket = file_transfer_bucket

    metrics = MetricsCollector(namespace="Tests")
    shared = SharedRedisCache(url=None)
    cache = TwoTierCache(
        local=LocalTTLCache(ttl_seconds=60, max_entries=128),
        shared=shared,
        shared_ttl_seconds=60,
    )
    repository = MemoryJobRepository()
    job_service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    return AppContainer(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared,
        authenticator=Authenticator(settings=settings, cache=cache),
        transfer_service=StubTransferService(),  # type: ignore[arg-type]
        job_repository=repository,
        job_service=job_service,
        activity_store=MemoryActivityStore(),
        idempotency_store=IdempotencyStore(
            cache=cache,
            enabled=True,
            ttl_seconds=300,
        ),
    )


def test_v1_health_and_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies v1 live/ready health and capability keys are exposed."""
    monkeypatch.setenv("FILE_TRANSFER_BUCKET", "")
    app = create_app(
        container_override=_build_v1_container(file_transfer_bucket="")
    )
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


def test_v1_jobs_create_list_get_retry_and_events() -> None:
    """Verifies v1 job create/list/get/retry/event lifecycle behavior."""
    app = create_app(container_override=_build_v1_container())
    with TestClient(app) as client:
        create_resp = client.post(
            "/v1/jobs",
            headers={"X-Session-Id": "scope-v1"},
            json={"job_type": "transform", "payload": {"input": "a"}},
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        job_id = created["job_id"]

        list_resp = client.get("/v1/jobs", headers={"X-Session-Id": "scope-v1"})
        assert list_resp.status_code == 200
        assert any(
            item["job_id"] == job_id for item in list_resp.json()["jobs"]
        )

        get_resp = client.get(
            f"/v1/jobs/{job_id}",
            headers={"X-Session-Id": "scope-v1"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["job"]["job_id"] == job_id

        retry_resp = client.post(
            f"/v1/jobs/{job_id}/retry",
            headers={"X-Session-Id": "scope-v1"},
        )
        assert retry_resp.status_code == 409

        events_resp = client.get(
            f"/v1/jobs/{job_id}/events",
            headers={"X-Session-Id": "scope-v1"},
        )
        assert events_resp.status_code == 200
        events = events_resp.json()["events"]
        assert len(events) == 1
        assert events[0]["job_id"] == job_id


def test_v1_resource_plan_and_release_info() -> None:
    """Verifies v1 resource planning plus release metadata contract."""
    app = create_app(container_override=_build_v1_container())
    with TestClient(app) as client:
        plan = client.post(
            "/v1/resources/plan", json={"resources": ["jobs", "unknown"]}
        )
        info = client.get("/v1/releases/info")

    assert plan.status_code == 200
    payload = plan.json()
    assert len(payload["plan"]) == 2
    unknown = [i for i in payload["plan"] if i["resource"] == "unknown"][0]
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
    app = create_app(container_override=_build_v1_container())
    with TestClient(app) as client:
        resp = client.post(
            "/v1/jobs",
            headers={
                "X-Session-Id": "scope-v1",
                "Idempotency-Key": "",
            },
            json={"job_type": "transform", "payload": {"input": "a"}},
        )
        whitespace_resp = client.post(
            "/v1/jobs",
            headers={
                "X-Session-Id": "scope-v1",
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
            "AUTH_MODE": AuthMode.SAME_ORIGIN.value,
            "JOBS_ENABLED": True,
        }
    )

    metrics = MetricsCollector(namespace="Tests")
    shared = SharedRedisCache(url=None)
    cache = TwoTierCache(
        local=LocalTTLCache(ttl_seconds=60, max_entries=128),
        shared=shared,
        shared_ttl_seconds=60,
    )
    repository = _FailingListJobRepository()
    job_service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    container = AppContainer(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared,
        authenticator=Authenticator(
            settings=settings,
            cache=cache,
        ),
        transfer_service=StubTransferService(),  # type: ignore[arg-type]
        job_repository=repository,
        job_service=job_service,
        activity_store=MemoryActivityStore(),
        idempotency_store=IdempotencyStore(
            cache=cache,
            enabled=False,
            ttl_seconds=300,
        ),
    )

    app = create_app(container_override=container)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/v1/jobs",
            headers={"X-Session-Id": "scope-1"},
        )

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "internal_error"
    assert payload["error"]["message"] == "unexpected internal error"
