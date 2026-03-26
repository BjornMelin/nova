"""Authorization contract tests for the /metrics/summary endpoint."""

from __future__ import annotations

import httpx
import pytest
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.config import Settings
from nova_file_api.errors import unauthorized
from nova_file_api.exports import (
    ExportService,
    MemoryExportPublisher,
    MemoryExportRepository,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import Principal

from .support.app import build_cache_stack, build_runtime_deps, build_test_app
from .support.doubles import StubTransferService

AUTH_HEADERS = {"Authorization": "Bearer token-123"}


class _StubAuthenticator:
    """Return a fixed principal for metrics summary authorization tests."""

    def __init__(self, *, permissions: tuple[str, ...]) -> None:
        self._permissions = permissions

    async def authenticate(
        self,
        *,
        token: str | None,
    ) -> Principal:
        if token is None or not token.strip():
            raise unauthorized("missing bearer token")
        return Principal(
            subject="caller-1",
            scope_id="scope-1",
            tenant_id=None,
            scopes=(),
            permissions=self._permissions,
        )


async def _request_metrics_summary(
    *,
    permissions: tuple[str, ...],
) -> httpx.Response:
    """Create a test app and return one /metrics/summary response."""
    settings = Settings.model_validate(
        {"IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency"}
    )

    metrics = MetricsCollector(namespace="Tests")
    metrics.incr("requests_total")
    metrics.observe_ms("exports_create_ms", 12.345)

    cache = build_cache_stack()
    export_repository = MemoryExportRepository()
    export_service = ExportService(
        repository=export_repository,
        publisher=MemoryExportPublisher(),
        metrics=metrics,
    )
    activity_store = MemoryActivityStore()
    await activity_store.record(
        principal=Principal(subject="caller-1", scope_id="scope-1"),
        event_type="exports_create",
    )

    app = build_test_app(
        build_runtime_deps(
            settings=settings,
            metrics=metrics,
            cache=cache,
            authenticator=_StubAuthenticator(permissions=permissions),
            transfer_service=StubTransferService(),
            export_service=export_service,
            activity_store=activity_store,
            idempotency_enabled=True,
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        return await client.get(
            "/metrics/summary",
            headers=AUTH_HEADERS,
        )


@pytest.mark.anyio
async def test_metrics_summary_rejects_missing_permission() -> None:
    """Bearer-authenticated metrics summary requires metrics:read."""
    response = await _request_metrics_summary(permissions=())
    assert response.status_code == 403
    payload = response.json()
    assert payload["error"]["code"] == "forbidden"
    assert payload["error"]["message"] == "missing metrics:read permission"


@pytest.mark.anyio
async def test_metrics_summary_allows_metrics_permission() -> None:
    """Bearer-authenticated metrics summary succeeds with metrics:read."""
    response = await _request_metrics_summary(
        permissions=("metrics:read",),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["counters"]["requests_total"] == 1
    assert payload["latencies_ms"]["exports_create_ms"] == 12.345
    assert payload["activity"]["events_total"] == 1
