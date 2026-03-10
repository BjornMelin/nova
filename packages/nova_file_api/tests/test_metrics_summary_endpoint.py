"""Authorization contract tests for the /metrics/summary endpoint."""

from __future__ import annotations

import httpx
import pytest
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.app import create_app
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
from nova_file_api.models import AuthMode, Principal
from starlette.requests import Request

from tests._test_doubles import StubTransferService


class _StubAuthenticator:
    """Return a fixed principal for metrics summary authorization tests."""

    def __init__(self, *, permissions: tuple[str, ...]) -> None:
        """Store the permissions exposed by the fake authenticator."""
        self._permissions = permissions

    async def authenticate(
        self,
        *,
        request: Request,
        session_id: str | None,
    ) -> Principal:
        """
        Return a fixed Principal used for metrics summary authorization tests.
        
        Parameters:
            request (Request): Ignored.
            session_id (str | None): Ignored.
        
        Returns:
            Principal: Principal with subject "caller-1", scope_id "scope-1", tenant_id None, empty scopes, and the permissions supplied to this authenticator.
        """
        del request, session_id
        return Principal(
            subject="caller-1",
            scope_id="scope-1",
            tenant_id=None,
            scopes=(),
            permissions=self._permissions,
        )


async def _build_container(
    *,
    auth_mode: AuthMode,
    permissions: tuple[str, ...],
) -> AppContainer:
    """
    Builds a minimal AppContainer configured for metrics summary tests.
    
    The returned container uses the provided authentication mode and a stub authenticator seeded with the given permissions, and includes prepopulated testing components (metrics with a single request counter and a latency sample, a two-tier cache with a shared redis stub, in-memory job repository/service and publisher, an activity store with one recorded "jobs_enqueue" event for subject "caller-1"/scope "scope-1", a stub transfer service, and an idempotency store enabled with a 300s TTL).
    
    Parameters:
        auth_mode (AuthMode): Authentication mode to set on the container.
        permissions (tuple[str, ...]): Permissions to assign to the stub authenticator.
    
    Returns:
        AppContainer: A fully constructed application container ready for metrics summary tests.
    """
    settings = Settings()
    settings.auth_mode = auth_mode

    metrics = MetricsCollector(namespace="Tests")
    metrics.incr("requests_total")
    metrics.observe_ms("jobs_enqueue_ms", 12.345)

    shared_cache = SharedRedisCache(url=None)
    cache = TwoTierCache(
        local=LocalTTLCache(ttl_seconds=60, max_entries=128),
        shared=shared_cache,
        shared_ttl_seconds=60,
    )
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

    return AppContainer(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared_cache,
        authenticator=(
            _StubAuthenticator(permissions=permissions)  # type: ignore[arg-type]
        ),
        transfer_service=StubTransferService(),  # type: ignore[arg-type]
        job_repository=job_repository,
        job_service=job_service,
        activity_store=activity_store,
        idempotency_store=IdempotencyStore(
            cache=cache,
            enabled=True,
            ttl_seconds=300,
        ),
    )


@pytest.mark.asyncio
async def test_metrics_summary_same_origin_allows_missing_permission() -> None:
    """SAME_ORIGIN allows metrics summary access without permissions."""
    app = create_app(
        container_override=await _build_container(
            auth_mode=AuthMode.SAME_ORIGIN,
            permissions=(),
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        response = await client.get("/metrics/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "counters": {"requests_total": 1},
        "latencies_ms": {"jobs_enqueue_ms": 12.345},
        "activity": {
            "events_total": 1,
            "active_users_today": 1,
            "distinct_event_types": 1,
        },
    }


@pytest.mark.asyncio
async def test_metrics_summary_non_same_origin_rejects_missing_permission() -> (
    None
):
    """JWT_LOCAL rejects metrics summary when metrics:read is missing."""
    app = create_app(
        container_override=await _build_container(
            auth_mode=AuthMode.JWT_LOCAL,
            permissions=(),
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        response = await client.get("/metrics/summary")
    assert response.status_code == 403
    payload = response.json()
    assert payload["error"]["code"] == "forbidden"
    assert payload["error"]["message"] == "missing metrics:read permission"


@pytest.mark.asyncio
async def test_metrics_summary_non_same_origin_allows_metrics_permission() -> (
    None
):
    """JWT_LOCAL allows metrics summary when metrics:read permission exists."""
    app = create_app(
        container_override=await _build_container(
            auth_mode=AuthMode.JWT_LOCAL,
            permissions=("metrics:read",),
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        response = await client.get("/metrics/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["counters"]["requests_total"] == 1
    assert payload["latencies_ms"]["jobs_enqueue_ms"] == 12.345
    assert payload["activity"]["events_total"] == 1
