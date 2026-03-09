from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.app import create_app
from nova_file_api.auth import Authenticator
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
from nova_file_api.models import AuthMode, IdempotencyMode

from ._test_doubles import StubAuthenticator, StubTransferService


class _SharedCacheUnavailable:
    async def ping(self) -> bool:
        return False


class _ActivityStoreUnavailable(MemoryActivityStore):
    def healthcheck(self) -> bool:
        return False


class _AuthDependencyUnavailable(StubAuthenticator):
    async def healthcheck(self) -> bool:
        return False


class _JobPublisherUnavailable(MemoryJobPublisher):
    def healthcheck(self) -> bool:
        return False


class _RemoteAuthNotReadyClient:
    requested_urls: list[str] = []

    def __init__(self, *, timeout: float) -> None:
        del timeout

    async def get(self, url: str) -> httpx.Response:
        type(self).requested_urls.append(url)
        return httpx.Response(503)

    async def aclose(self) -> None:
        return None


def _build_container(
    *,
    jobs_enabled: bool = True,
    file_transfer_bucket: str = "test-transfer-bucket",
    auth_mode: AuthMode = AuthMode.SAME_ORIGIN,
    idempotency_mode: IdempotencyMode = IdempotencyMode.LOCAL_ONLY,
) -> AppContainer:
    """Build an app container with in-memory test doubles."""
    settings = Settings()
    settings.jobs_enabled = jobs_enabled
    settings.file_transfer_bucket = file_transfer_bucket
    settings.auth_mode = auth_mode
    settings.idempotency_mode = idempotency_mode
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
            mode=settings.idempotency_mode,
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
        "job_queue": True,
        "activity_store": True,
        "auth_dependency": True,
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
        "job_queue": True,
        "activity_store": True,
        "auth_dependency": True,
    }


def test_readyz_fails_when_bucket_is_missing() -> None:
    """Verify readiness fails when FILE_TRANSFER_BUCKET is not configured."""
    app = create_app(
        container_override=_build_container(file_transfer_bucket="")
    )
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


def test_readyz_keeps_noncritical_checks_observable() -> None:
    """Verify shared cache and activity health remain observable only."""
    container = _build_container()
    container.shared_cache = _SharedCacheUnavailable()  # type: ignore[assignment]
    container.activity_store = _ActivityStoreUnavailable()
    app = create_app(container_override=container)
    with TestClient(app) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": False,
        "job_queue": True,
        "activity_store": False,
        "auth_dependency": True,
    }


def test_readyz_fails_when_shared_cache_is_required_and_unavailable() -> None:
    container = _build_container(
        idempotency_mode=IdempotencyMode.SHARED_REQUIRED
    )
    container.shared_cache = _SharedCacheUnavailable()  # type: ignore[assignment]
    app = create_app(container_override=container)
    with TestClient(app) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": False,
        "job_queue": True,
        "activity_store": True,
        "auth_dependency": True,
    }


def test_readyz_fails_when_job_queue_is_unavailable() -> None:
    """Verify readiness fails when the jobs queue dependency is down."""
    container = _build_container()
    container.job_service.publisher = _JobPublisherUnavailable()
    app = create_app(container_override=container)
    with TestClient(app) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": True,
        "job_queue": False,
        "activity_store": True,
        "auth_dependency": True,
    }


def test_readyz_fails_when_auth_dependency_is_unavailable() -> None:
    """Verify auth dependency failures still gate readiness."""
    container = _build_container()
    container.authenticator = _AuthDependencyUnavailable()  # type: ignore[assignment]
    app = create_app(container_override=container)
    with TestClient(app) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": True,
        "job_queue": True,
        "activity_store": True,
        "auth_dependency": False,
    }


def test_readyz_fails_when_local_jwt_auth_is_misconfigured() -> None:
    """Verify JWT local mode readiness fails on missing verifier config."""
    container = _build_container(auth_mode=AuthMode.JWT_LOCAL)
    container.authenticator = Authenticator(
        settings=container.settings,
        cache=container.cache,
    )
    app = create_app(container_override=container)
    with TestClient(app) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": True,
        "job_queue": True,
        "activity_store": True,
        "auth_dependency": False,
    }


def test_readyz_fails_when_remote_auth_ready_check_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = _build_container(auth_mode=AuthMode.JWT_REMOTE)
    container.settings.remote_auth_base_url = "https://auth.example.local"
    container.authenticator = Authenticator(
        settings=container.settings,
        cache=container.cache,
    )
    _RemoteAuthNotReadyClient.requested_urls = []

    monkeypatch.setattr(
        "nova_file_api.auth.httpx.AsyncClient", _RemoteAuthNotReadyClient
    )

    app = create_app(container_override=container)
    with TestClient(app) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": True,
        "job_queue": True,
        "activity_store": True,
        "auth_dependency": False,
    }
    assert _RemoteAuthNotReadyClient.requested_urls == [
        "https://auth.example.local/v1/health/ready"
    ]


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
