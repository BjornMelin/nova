"""Authorization contract tests for the /metrics/summary endpoint."""

from __future__ import annotations

import httpx
import pytest
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.config import Settings
from nova_file_api.jobs import (
    JobService,
    MemoryJobPublisher,
    MemoryJobRepository,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import AuthMode, Principal
from starlette.requests import Request

from .support.app import build_cache_stack, build_runtime_deps, build_test_app
from .support.doubles import StubTransferService


class _StubAuthenticator:
    """Return a fixed principal for metrics summary authorization tests."""

    def __init__(self, *, permissions: tuple[str, ...]) -> None:
        self._permissions = permissions

    async def authenticate(
        self,
        *,
        request: Request,
        session_id: str | None,
    ) -> Principal:
        del request, session_id
        return Principal(
            subject="caller-1",
            scope_id="scope-1",
            tenant_id=None,
            scopes=(),
            permissions=self._permissions,
        )


async def _request_metrics_summary(
    *,
    auth_mode: AuthMode,
    permissions: tuple[str, ...],
) -> httpx.Response:
    """Create a test app and return one /metrics/summary response."""
    settings = Settings()
    settings.auth_mode = auth_mode

    metrics = MetricsCollector(namespace="Tests")
    metrics.incr("requests_total")
    metrics.observe_ms("jobs_enqueue_ms", 12.345)

    shared_cache, cache = build_cache_stack()
    job_repository = MemoryJobRepository()
    job_service = JobService(
        repository=job_repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    activity_store = MemoryActivityStore()
    await activity_store.record(
        principal=Principal(subject="caller-1", scope_id="scope-1"),
        event_type="jobs_enqueue",
    )

    app = build_test_app(
        build_runtime_deps(
            settings=settings,
            metrics=metrics,
            shared_cache=shared_cache,
            cache=cache,
            authenticator=_StubAuthenticator(permissions=permissions),
            transfer_service=StubTransferService(),
            job_service=job_service,
            activity_store=activity_store,
            idempotency_enabled=True,
            use_in_memory_shared_cache=True,
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        return await client.get("/metrics/summary")


@pytest.mark.asyncio
async def test_metrics_summary_same_origin_allows_missing_permission() -> None:
    """SAME_ORIGIN allows metrics summary access without permissions."""
    response = await _request_metrics_summary(
        auth_mode=AuthMode.SAME_ORIGIN,
        permissions=(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) >= {"counters", "latencies_ms", "activity"}
    assert payload["counters"]["requests_total"] >= 1
    assert "jobs_enqueue_ms" in payload["latencies_ms"]
    assert payload["activity"]["events_total"] >= 1


@pytest.mark.asyncio
async def test_metrics_summary_non_same_origin_rejects_missing_permission() -> (
    None
):
    """JWT_LOCAL rejects metrics summary when metrics:read is missing."""
    response = await _request_metrics_summary(
        auth_mode=AuthMode.JWT_LOCAL,
        permissions=(),
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["error"]["code"] == "forbidden"
    assert payload["error"]["message"] == "missing metrics:read permission"


@pytest.mark.asyncio
async def test_metrics_summary_non_same_origin_allows_metrics_permission() -> (
    None
):
    """JWT_LOCAL allows metrics summary when metrics:read permission exists."""
    response = await _request_metrics_summary(
        auth_mode=AuthMode.JWT_LOCAL,
        permissions=("metrics:read",),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["counters"]["requests_total"] == 1
    assert payload["latencies_ms"]["jobs_enqueue_ms"] == 12.345
    assert payload["activity"]["events_total"] == 1
