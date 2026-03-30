"""Golden-flow auth canary tests for public and protected routes."""

from __future__ import annotations

import pytest

from .support.app import build_test_app, request_app
from .test_v1_api import AUTH_HEADERS, EXPORT_REQUEST, _build_v1_deps


@pytest.mark.anyio
async def test_browser_canary_keeps_public_and_protected_flows_coherent() -> (
    None
):
    """Public metadata and protected exports should both honor app auth."""
    app = build_test_app(_build_v1_deps())

    release_response = await request_app(
        app,
        "GET",
        "/v1/releases/info",
        headers={"Origin": "https://app.example.com"},
    )
    unauthorized_response = await request_app(
        app,
        "POST",
        "/v1/exports",
        headers={"Origin": "https://app.example.com"},
        json=EXPORT_REQUEST,
    )
    authorized_response = await request_app(
        app,
        "POST",
        "/v1/exports",
        headers={**AUTH_HEADERS, "Origin": "https://app.example.com"},
        json=EXPORT_REQUEST,
    )

    assert release_response.status_code == 200
    assert (
        release_response.headers["access-control-allow-origin"]
        == "https://app.example.com"
    )
    assert unauthorized_response.status_code == 401
    assert (
        unauthorized_response.headers["access-control-allow-origin"]
        == "https://app.example.com"
    )
    assert authorized_response.status_code == 201
    assert (
        authorized_response.headers["access-control-allow-origin"]
        == "https://app.example.com"
    )
