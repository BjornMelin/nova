from __future__ import annotations

from typing import cast

import httpx
import pytest

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.auth import Authenticator
from nova_file_api.config import Settings
from nova_file_api.exports import (
    ExportService,
    MemoryExportPublisher,
    MemoryExportRepository,
)
from nova_file_api.idempotency import IdempotencyStore
from nova_runtime_support.metrics import MetricsCollector

from .support.app import (
    RuntimeDeps,
    build_cache_stack,
    build_runtime_deps,
    build_test_app,
    request_app,
)
from .support.doubles import StubAuthenticator, StubTransferService

AUTH_HEADERS = {"Authorization": "Bearer token-123"}


class _FailingIdempotencyStore:
    enabled = True

    async def healthcheck(self) -> bool:
        return False


class _FailingActivityStore(MemoryActivityStore):
    async def healthcheck(self) -> bool:
        return False


def _build_deps(
    *,
    exports_enabled: bool = True,
    file_transfer_bucket: str = "test-transfer-bucket",
) -> RuntimeDeps:
    """Build in-memory test doubles for readiness and health checks."""
    settings = Settings.model_validate(
        {"IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency"}
    )
    settings.exports_enabled = exports_enabled
    settings.file_transfer_bucket = file_transfer_bucket
    metrics = MetricsCollector(namespace="Tests")
    cache = build_cache_stack()
    export_service = ExportService(
        repository=MemoryExportRepository(),
        publisher=MemoryExportPublisher(),
        metrics=metrics,
    )
    return build_runtime_deps(
        settings=settings,
        metrics=metrics,
        cache=cache,
        authenticator=StubAuthenticator(),
        transfer_service=StubTransferService(),
        export_service=export_service,
        activity_store=MemoryActivityStore(),
        idempotency_enabled=True,
    )


def _replace_idempotency_store_for_readiness(
    *,
    deps: RuntimeDeps,
    idempotency_store: _FailingIdempotencyStore,
) -> None:
    """Replace the runtime idempotency store used by readiness checks."""
    deps.idempotency_store = cast(IdempotencyStore, idempotency_store)


@pytest.mark.anyio
async def test_v1_health_live_returns_ok() -> None:
    """Verify `/v1/health/live` returns 200 with an ok payload."""
    app = build_test_app(_build_deps())
    response = await request_app(app, "GET", "/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.anyio
async def test_v1_health_ready_returns_expected_checks() -> None:
    """Verify `/v1/health/ready` exposes expected readiness checks."""
    app = build_test_app(_build_deps())
    response = await request_app(app, "GET", "/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["checks"] == {
        "bucket_configured": True,
        "idempotency_store": True,
        "export_runtime": True,
        "activity_store": True,
        "transfer_runtime": True,
        "auth_dependency": True,
    }


@pytest.mark.anyio
async def test_readyz_stays_ok_when_exports_are_disabled() -> None:
    """Verify feature flags do not force readiness false."""
    app = build_test_app(_build_deps(exports_enabled=False))
    response = await request_app(app, "GET", "/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["checks"] == {
        "bucket_configured": True,
        "idempotency_store": True,
        "export_runtime": True,
        "activity_store": True,
        "transfer_runtime": True,
        "auth_dependency": True,
    }


@pytest.mark.anyio
async def test_readyz_idempotency_store_not_gate_when_idempotency_off() -> None:
    """Idempotency-store outages stay visible when idempotency is off."""
    deps = _build_deps()
    deps.settings.idempotency_enabled = False
    _replace_idempotency_store_for_readiness(
        deps=deps,
        idempotency_store=_FailingIdempotencyStore(),
    )
    app = build_test_app(deps)

    response = await request_app(app, "GET", "/v1/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["checks"] == {
        "bucket_configured": True,
        "idempotency_store": False,
        "export_runtime": True,
        "activity_store": True,
        "transfer_runtime": True,
        "auth_dependency": True,
    }


@pytest.mark.anyio
async def test_readyz_fails_when_idempotency_requires_store() -> None:
    """Idempotency-store outages fail readiness when idempotency is enabled."""
    deps = _build_deps()
    _replace_idempotency_store_for_readiness(
        deps=deps,
        idempotency_store=_FailingIdempotencyStore(),
    )
    app = build_test_app(deps)

    response = await request_app(app, "GET", "/v1/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["ok"] is False
    assert payload["checks"] == {
        "bucket_configured": True,
        "idempotency_store": False,
        "export_runtime": True,
        "activity_store": True,
        "transfer_runtime": True,
        "auth_dependency": True,
    }


@pytest.mark.anyio
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
        "idempotency_store": True,
        "export_runtime": True,
        "activity_store": False,
        "transfer_runtime": True,
        "auth_dependency": True,
    }


@pytest.mark.anyio
async def test_readyz_fails_when_bucket_is_missing() -> None:
    """Verify readiness fails when FILE_TRANSFER_BUCKET is not configured."""
    app = build_test_app(_build_deps(file_transfer_bucket=""))
    response = await request_app(app, "GET", "/v1/health/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["ok"] is False
    assert payload["checks"] == {
        "bucket_configured": False,
        "idempotency_store": True,
        "export_runtime": True,
        "activity_store": True,
        "transfer_runtime": True,
        "auth_dependency": True,
    }


@pytest.mark.anyio
async def test_readyz_fails_when_oidc_bearer_settings_are_incomplete() -> None:
    """Verify bearer-verifier readiness fails closed without full OIDC."""
    deps = _build_deps()
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
        "idempotency_store": True,
        "export_runtime": True,
        "activity_store": True,
        "transfer_runtime": True,
        "auth_dependency": False,
    }


@pytest.mark.anyio
async def test_validation_errors_use_canonical_error_envelope() -> None:
    """Verify request validation failures return the standard error envelope."""
    app = build_test_app(_build_deps())
    response = await request_app(
        app,
        "POST",
        "/v1/exports",
        headers={
            **AUTH_HEADERS,
            "X-Request-Id": "req-transfer-422",
        },
        json={
            "source_key": "",
        },
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "invalid_request"
    assert response.headers["X-Request-Id"] == "req-transfer-422"
    assert payload["error"]["request_id"] == "req-transfer-422"
    assert payload["error"]["details"]["errors"]


async def _request_exports_with_raw_body(
    *,
    content: str,
    headers: dict[str, str],
) -> httpx.Response:
    """POST ``/v1/exports`` with a raw string body and custom headers.

    Args:
        content: Serialized request body (e.g. JSON) sent as-is.
        headers: HTTP headers for the request (must include auth as needed).

    Returns:
        The ``httpx.Response`` from the ASGI app.
    """
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
            "/v1/exports",
            headers=headers,
            content=content,
        )


@pytest.mark.anyio
async def test_validation_errors_stay_canonical_without_content_type() -> None:
    """Missing content type should still serialize as canonical 422."""
    response = await _request_exports_with_raw_body(
        content='{"source_key":"uploads/scope-1/source.csv","filename":"source.csv"}',
        headers={**AUTH_HEADERS, "X-Request-Id": "req-missing-ct"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "invalid_request"
    assert response.headers["X-Request-Id"] == "req-missing-ct"
    assert payload["error"]["request_id"] == "req-missing-ct"
    assert payload["error"]["details"]["errors"]


@pytest.mark.anyio
async def test_validation_errors_stay_canonical_for_wrong_content_type() -> (
    None
):
    """Wrong content type should still serialize as canonical 422."""
    response = await _request_exports_with_raw_body(
        content='{"source_key":"uploads/scope-1/source.csv","filename":"source.csv"}',
        headers={
            **AUTH_HEADERS,
            "Content-Type": "text/plain",
            "X-Request-Id": "req-wrong-ct",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "invalid_request"
    assert response.headers["X-Request-Id"] == "req-wrong-ct"
    assert payload["error"]["request_id"] == "req-wrong-ct"
    assert payload["error"]["details"]["errors"]


@pytest.mark.anyio
async def test_success_responses_echo_request_id_header() -> None:
    """Successful responses should echo caller request IDs in headers."""
    app = build_test_app(_build_deps())
    response = await request_app(
        app,
        "GET",
        "/v1/health/live",
        headers={"X-Request-Id": "req-live-ok"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "req-live-ok"


@pytest.mark.anyio
async def test_success_responses_generate_request_id_header() -> None:
    """Successful responses should mint a request ID when none is provided."""
    app = build_test_app(_build_deps())
    response = await request_app(app, "GET", "/v1/health/live")

    assert response.status_code == 200
    assert response.headers["X-Request-Id"]
