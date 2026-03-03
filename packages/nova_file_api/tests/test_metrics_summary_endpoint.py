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
from nova_file_api.models import AuthMode, Principal
from starlette.requests import Request

from ._test_doubles import StubTransferService


class _StubAuthenticator:
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


def _build_container(
    *,
    auth_mode: AuthMode,
    permissions: tuple[str, ...],
) -> AppContainer:
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
    activity_store.record(
        principal=Principal(subject="caller-1", scope_id="scope-1"),
        event_type="jobs_enqueue",
    )

    return AppContainer(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared_cache,
        authenticator=_StubAuthenticator(permissions=permissions),  # type: ignore[arg-type]
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


def test_metrics_summary_same_origin_allows_missing_permission() -> None:
    app = create_app(
        container_override=_build_container(
            auth_mode=AuthMode.SAME_ORIGIN,
            permissions=(),
        )
    )
    with TestClient(app) as client:
        response = client.get("/metrics/summary")
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


def test_metrics_summary_non_same_origin_rejects_missing_permission() -> None:
    app = create_app(
        container_override=_build_container(
            auth_mode=AuthMode.JWT_LOCAL,
            permissions=(),
        )
    )
    with TestClient(app) as client:
        response = client.get("/metrics/summary")
    assert response.status_code == 403
    payload = response.json()
    assert payload["error"]["code"] == "forbidden"
    assert payload["error"]["message"] == "missing metrics:read permission"


def test_metrics_summary_non_same_origin_allows_metrics_permission() -> None:
    app = create_app(
        container_override=_build_container(
            auth_mode=AuthMode.JWT_LOCAL,
            permissions=("metrics:read",),
        )
    )
    with TestClient(app) as client:
        response = client.get("/metrics/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["counters"]["requests_total"] == 1
    assert payload["latencies_ms"]["jobs_enqueue_ms"] == 12.345
    assert payload["activity"]["events_total"] == 1
