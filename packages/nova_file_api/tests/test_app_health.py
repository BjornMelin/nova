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
from nova_file_api.models import Principal
from starlette.requests import Request


class _StubAuthenticator:
    """Stub authenticator that always returns a fixed principal."""

    async def authenticate(
        self,
        *,
        request: Request,
        session_id: str | None,
    ) -> Principal:
        """Return a deterministic principal for tests."""
        del request, session_id
        return Principal(
            subject="user-1",
            scope_id="scope-1",
            tenant_id=None,
            scopes=(),
            permissions=("metrics:read",),
        )


class _StubTransferService:
    """Placeholder transfer service for container wiring tests."""


def _build_container(*, jobs_enabled: bool = True) -> AppContainer:
    """Build an app container with in-memory test doubles."""
    settings = Settings()
    settings.jobs_enabled = jobs_enabled
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
        authenticator=_StubAuthenticator(),  # type: ignore[arg-type]
        transfer_service=_StubTransferService(),  # type: ignore[arg-type]
        job_repository=repo,
        job_service=jobs,
        activity_store=MemoryActivityStore(),
        idempotency_store=IdempotencyStore(
            cache=cache,
            enabled=True,
            ttl_seconds=300,
        ),
    )


def test_healthz_returns_ok() -> None:
    """Verify `/healthz` returns 200 with an ok payload."""
    app = create_app(container_override=_build_container())
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_readyz_returns_expected_checks() -> None:
    """Verify `/readyz` exposes expected readiness checks."""
    app = create_app(container_override=_build_container())
    with TestClient(app) as client:
        response = client.get("/readyz")
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
        response = client.get("/readyz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": True,
    }
