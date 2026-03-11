from __future__ import annotations

from fastapi.testclient import TestClient
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.auth import Authenticator
from nova_file_api.config import Settings
from nova_file_api.jobs import (
    JobService,
    MemoryJobPublisher,
    MemoryJobRepository,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import AuthMode

from .support.app import (
    RuntimeDeps,
    build_cache_stack,
    build_runtime_deps,
    build_test_app,
)
from .support.doubles import StubAuthenticator, StubTransferService


def _build_deps(
    *,
    jobs_enabled: bool = True,
    file_transfer_bucket: str = "test-transfer-bucket",
) -> RuntimeDeps:
    """Build in-memory test doubles for readiness and health checks."""
    settings = Settings()
    settings.jobs_enabled = jobs_enabled
    settings.file_transfer_bucket = file_transfer_bucket
    metrics = MetricsCollector(namespace="Tests")
    shared, cache = build_cache_stack()
    job_service = JobService(
        repository=MemoryJobRepository(),
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
    )


def test_v1_health_live_returns_ok() -> None:
    """Verify `/v1/health/live` returns 200 with an ok payload."""
    app = build_test_app(_build_deps())
    with TestClient(app) as client:
        response = client.get("/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_v1_health_ready_returns_expected_checks() -> None:
    """Verify `/v1/health/ready` exposes expected readiness checks."""
    app = build_test_app(_build_deps())
    with TestClient(app) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": True,
        "job_queue": True,
        "activity_store": True,
        "auth_dependency": True,
    }


def test_readyz_stays_ok_when_jobs_are_disabled() -> None:
    """Verify feature flags do not force readiness false."""
    app = build_test_app(_build_deps(jobs_enabled=False))
    with TestClient(app) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": True,
        "job_queue": True,
        "activity_store": True,
        "auth_dependency": True,
    }


def test_readyz_fails_when_bucket_is_missing() -> None:
    """Verify readiness fails when FILE_TRANSFER_BUCKET is not configured."""
    app = build_test_app(_build_deps(file_transfer_bucket=""))
    with TestClient(app) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["ok"] is False
    assert payload["checks"] == {
        "bucket_configured": False,
        "shared_cache": True,
        "job_queue": True,
        "activity_store": True,
        "auth_dependency": True,
    }


def test_readyz_fails_when_jwt_local_oidc_settings_are_incomplete() -> None:
    """Verify jwt_local readiness fails closed without full OIDC config."""
    deps = _build_deps()
    deps.settings.auth_mode = AuthMode.JWT_LOCAL
    deps.settings.oidc_issuer = "https://issuer.example/"
    deps.settings.oidc_audience = None
    deps.settings.oidc_jwks_url = None
    deps.authenticator = Authenticator(
        settings=deps.settings,
        cache=deps.cache,
    )
    app = build_test_app(deps)

    with TestClient(app) as client:
        response = client.get("/v1/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["ok"] is False
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": True,
        "job_queue": True,
        "activity_store": True,
        "auth_dependency": False,
    }


def test_validation_errors_use_canonical_error_envelope() -> None:
    """Verify request validation failures return the standard error envelope."""
    app = build_test_app(_build_deps())
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
