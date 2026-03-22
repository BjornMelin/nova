from __future__ import annotations

import httpx
import pytest
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.auth import Authenticator
from nova_file_api.cache import SharedRedisCache
from nova_file_api.config import Settings
from nova_file_api.dependencies import build_two_tier_cache
from nova_file_api.idempotency import IdempotencyStore
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
    request_app,
)
from .support.doubles import StubAuthenticator, StubTransferService

AUTH_HEADERS = {"Authorization": "Bearer token-123"}


class _FailingSharedCache(SharedRedisCache):
    def __init__(self) -> None:
        super().__init__(url=None)

    async def ping(self) -> bool:
        return False


class _FailingActivityStore(MemoryActivityStore):
    async def healthcheck(self) -> bool:
        return False


def _build_deps(
    *,
    jobs_enabled: bool = True,
    file_transfer_bucket: str = "test-transfer-bucket",
) -> RuntimeDeps:
    """Build in-memory test doubles for readiness and health checks."""
    settings = Settings.model_validate({})
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
        use_in_memory_shared_cache=True,
    )


def _rebind_shared_cache_for_readiness(
    *,
    deps: RuntimeDeps,
    shared_cache: SharedRedisCache,
) -> None:
    """Rebind cache and idempotency store to a replacement shared cache."""
    deps.shared_cache = shared_cache
    deps.cache = build_two_tier_cache(
        settings=deps.settings,
        metrics=deps.metrics,
        shared_cache=shared_cache,
    )
    deps.idempotency_store = IdempotencyStore(
        shared_cache=shared_cache,
        enabled=deps.settings.idempotency_enabled,
        ttl_seconds=deps.settings.idempotency_ttl_seconds,
        key_prefix=deps.settings.cache_key_prefix,
        key_schema_version=deps.settings.cache_key_schema_version,
    )


@pytest.mark.asyncio
async def test_v1_health_live_returns_ok() -> None:
    """Verify `/v1/health/live` returns 200 with an ok payload."""
    app = build_test_app(_build_deps())
    response = await request_app(app, "GET", "/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_v1_health_ready_returns_expected_checks() -> None:
    """Verify `/v1/health/ready` exposes expected readiness checks."""
    app = build_test_app(_build_deps())
    response = await request_app(app, "GET", "/v1/health/ready")
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


@pytest.mark.asyncio
async def test_readyz_stays_ok_when_jobs_are_disabled() -> None:
    """Verify feature flags do not force readiness false."""
    app = build_test_app(_build_deps(jobs_enabled=False))
    response = await request_app(app, "GET", "/v1/health/ready")
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


@pytest.mark.asyncio
async def test_readyz_shared_cache_not_gate_when_idempotency_off() -> None:
    """Shared-cache outages stay visible when idempotency is off."""
    deps = _build_deps()
    deps.settings.idempotency_enabled = False
    _rebind_shared_cache_for_readiness(
        deps=deps,
        shared_cache=_FailingSharedCache(),
    )
    app = build_test_app(deps)

    response = await request_app(app, "GET", "/v1/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": False,
        "job_queue": True,
        "activity_store": True,
        "auth_dependency": True,
    }


@pytest.mark.asyncio
async def test_readyz_fails_when_idempotency_requires_shared_cache() -> None:
    """Shared-cache outages fail readiness when idempotency is enabled."""
    deps = _build_deps()
    _rebind_shared_cache_for_readiness(
        deps=deps,
        shared_cache=_FailingSharedCache(),
    )
    app = build_test_app(deps)

    response = await request_app(app, "GET", "/v1/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["ok"] is False
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": False,
        "job_queue": True,
        "activity_store": True,
        "auth_dependency": True,
    }


@pytest.mark.asyncio
async def test_readyz_reports_activity_store_failures_without_gating() -> None:
    """Activity-store degradation should remain diagnostic in readiness."""
    deps = _build_deps()
    deps.activity_store = _FailingActivityStore()
    app = build_test_app(deps)

    response = await request_app(app, "GET", "/v1/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["checks"] == {
        "bucket_configured": True,
        "shared_cache": True,
        "job_queue": True,
        "activity_store": False,
        "auth_dependency": True,
    }


@pytest.mark.asyncio
async def test_readyz_fails_when_bucket_is_missing() -> None:
    """Verify readiness fails when FILE_TRANSFER_BUCKET is not configured."""
    app = build_test_app(_build_deps(file_transfer_bucket=""))
    response = await request_app(app, "GET", "/v1/health/ready")
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


@pytest.mark.asyncio
async def test_readyz_fails_when_jwt_local_oidc_settings_are_incomplete() -> (
    None
):
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

    response = await request_app(app, "GET", "/v1/health/ready")

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


@pytest.mark.asyncio
async def test_validation_errors_use_canonical_error_envelope() -> None:
    """Verify request validation failures return the standard error envelope."""
    app = build_test_app(_build_deps())
    response = await request_app(
        app,
        "POST",
        "/v1/jobs",
        headers={
            **AUTH_HEADERS,
            "X-Request-Id": "req-transfer-422",
        },
        json={
            "job_type": "",
        },
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["request_id"] == "req-transfer-422"
    assert payload["error"]["details"]["errors"]


async def _request_jobs_with_raw_body(
    *,
    content: str,
    headers: dict[str, str],
) -> httpx.Response:
    app = build_test_app(_build_deps())
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=app,
                raise_app_exceptions=False,
            ),
            base_url="http://testserver",
        ) as client,
    ):
        return await client.post(
            "/v1/jobs",
            headers=headers,
            content=content,
        )


@pytest.mark.asyncio
async def test_validation_errors_stay_canonical_without_content_type() -> None:
    """Missing content type should still serialize as canonical 422."""
    response = await _request_jobs_with_raw_body(
        content='{"job_type":"test","payload":{}}',
        headers={**AUTH_HEADERS, "X-Request-Id": "req-missing-ct"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["request_id"] == "req-missing-ct"
    assert payload["error"]["details"]["errors"]


@pytest.mark.asyncio
async def test_validation_errors_stay_canonical_for_wrong_content_type() -> (
    None
):
    """Wrong content type should still serialize as canonical 422."""
    response = await _request_jobs_with_raw_body(
        content='{"job_type":"test","payload":{}}',
        headers={
            **AUTH_HEADERS,
            "Content-Type": "text/plain",
            "X-Request-Id": "req-wrong-ct",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["request_id"] == "req-wrong-ct"
    assert payload["error"]["details"]["errors"]
