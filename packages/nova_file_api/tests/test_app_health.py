from __future__ import annotations

from fastapi.testclient import TestClient
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.app import create_app
from nova_file_api.cache import (
    LocalTTLCache,
    SharedRedisCache,
    TwoTierCache,
)
from nova_file_api.config import Settings
from nova_file_api.container import AppContainer
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.jobs import (
    JobService,
    MemoryJobPublisher,
    MemoryJobRepository,
)
from nova_file_api.metrics import MetricsCollector

from ._test_doubles import StubAuthenticator, StubTransferService


def _build_container(
    *,
    jobs_enabled: bool = True,
    file_transfer_bucket: str = "test-transfer-bucket",
) -> AppContainer:
    """Build an app container with in-memory test doubles."""
    settings = Settings()
    settings.jobs_enabled = jobs_enabled
    settings.file_transfer_bucket = file_transfer_bucket
    metrics = MetricsCollector(namespace="Tests")
    shared = SharedRedisCache(url=None)
    cache = TwoTierCache(
        local=LocalTTLCache(ttl_seconds=60, max_entries=128),
        shared=shared,
        shared_ttl_seconds=60,
    )
    repo = MemoryJobRepository()
    jobs = JobService(
        repository=repo,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    return AppContainer(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared,
        authenticator=StubAuthenticator(),  # type: ignore[arg-type]
        transfer_service=StubTransferService(),  # type: ignore[arg-type]
        job_repository=repo,
        job_service=jobs,
        activity_store=MemoryActivityStore(),
        idempotency_store=IdempotencyStore(
            cache=cache,
            enabled=True,
            ttl_seconds=300,
        ),
    )


def test_v1_health_live_returns_ok() -> None:
    """Verify `/v1/health/live` returns 200 with an ok payload."""
    app = create_app(container_override=_build_container())
    with TestClient(app) as client:
        response = client.get("/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_v1_health_ready_returns_expected_checks() -> None:
    """Verify `/v1/health/ready` exposes expected readiness checks."""
    app = create_app(container_override=_build_container())
    with TestClient(app) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": True,
    }


def test_readyz_stays_ok_when_jobs_are_disabled() -> None:
    """Verify feature flags do not force readiness false."""
    app = create_app(container_override=_build_container(jobs_enabled=False))
    with TestClient(app) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": True,
    }


def test_readyz_fails_when_bucket_is_missing() -> None:
    """Verify readiness fails when FILE_TRANSFER_BUCKET is not configured."""
    app = create_app(
        container_override=_build_container(file_transfer_bucket="")
    )
    with TestClient(app) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["checks"] == {
        "bucket_configured": False,
        "shared_cache": True,
    }


def test_validation_errors_use_canonical_error_envelope() -> None:
    """Verify request validation failures return the standard error envelope."""
    app = create_app(container_override=_build_container())
    with TestClient(app) as client:
        response = client.post(
            "/v1/jobs",
            headers={"X-Request-Id": "req-transfer-422"},
            json={
                "job_type": "",
            },
        )
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["request_id"] == "req-transfer-422"
    assert payload["error"]["details"]["errors"]
