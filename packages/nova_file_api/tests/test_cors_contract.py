"""Browser-facing CORS contract tests for the FastAPI runtime."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.config import Settings
from nova_file_api.exports import (
    ExportService,
    MemoryExportPublisher,
    MemoryExportRepository,
)
from nova_runtime_support.metrics import MetricsCollector

from .support.app import (
    build_cache_stack,
    build_runtime_deps,
    build_test_app,
    request_app,
)
from .support.doubles import StubAuthenticator, StubTransferService


def _build_app() -> FastAPI:
    settings = Settings.model_validate(
        {
            "exports_enabled": True,
            "idempotency_dynamodb_table": "test-idempotency",
            "cors_allowed_origins": ["https://app.example.com"],
            "environment": "prod",
        }
    )
    metrics = MetricsCollector(namespace="Tests")
    cache = build_cache_stack()
    repository = MemoryExportRepository()
    return build_test_app(
        build_runtime_deps(
            settings=settings,
            metrics=metrics,
            cache=cache,
            authenticator=StubAuthenticator(),
            transfer_service=StubTransferService(),
            export_service=ExportService(
                repository=repository,
                publisher=MemoryExportPublisher(),
                metrics=metrics,
            ),
            activity_store=MemoryActivityStore(),
            idempotency_enabled=True,
        )
    )


@pytest.mark.anyio
async def test_cors_preflight_allows_browser_headers_for_exports() -> None:
    """Preflight requests should allow the browser headers the client uses."""
    app = _build_app()

    response = await request_app(
        app,
        "OPTIONS",
        "/v1/exports",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "authorization,content-type,idempotency-key"
            ),
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://app.example.com"
    )
    assert "POST" in response.headers["access-control-allow-methods"]
    assert (
        "authorization"
        in response.headers["access-control-allow-headers"].lower()
    )
    assert response.headers.get("access-control-allow-credentials") != "true"


@pytest.mark.anyio
async def test_cors_rejects_unknown_origin() -> None:
    """Preflight requests from untrusted origins should be rejected."""
    app = _build_app()

    response = await request_app(
        app,
        "OPTIONS",
        "/v1/exports",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
