"""OpenAPI contract regression tests for route cutover and schema build."""

from __future__ import annotations

from fastapi.testclient import TestClient
from nova_file_api.app import create_app


def test_openapi_contains_split_routes_and_no_legacy_prefix() -> None:
    """OpenAPI should expose only split transfer and jobs routes."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200

    payload = response.json()
    paths = payload.get("paths", {})
    assert isinstance(paths, dict)

    expected_paths = {
        "/api/transfers/uploads/initiate",
        "/api/transfers/uploads/sign-parts",
        "/api/transfers/uploads/complete",
        "/api/transfers/uploads/abort",
        "/api/transfers/downloads/presign",
        "/api/jobs/enqueue",
        "/api/jobs/{job_id}",
        "/api/jobs/{job_id}/cancel",
        "/api/jobs/{job_id}/result",
        "/healthz",
        "/readyz",
        "/metrics/summary",
        "/v1/jobs",
        "/v1/jobs/{job_id}",
        "/v1/jobs/{job_id}/retry",
        "/v1/jobs/{job_id}/events",
        "/v1/capabilities",
        "/v1/resources/plan",
        "/v1/releases/info",
        "/v1/health/live",
        "/v1/health/ready",
    }
    assert set(paths) == expected_paths


def test_openapi_schema_generation_smoke() -> None:
    """OpenAPI schema should build via app factory without exceptions."""
    app = create_app()
    schema = app.openapi()
    assert isinstance(schema, dict)
    assert schema.get("openapi") == "3.1.0"
