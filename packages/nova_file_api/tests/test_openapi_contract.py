"""OpenAPI contract regression tests for route cutover and schema build."""

from __future__ import annotations

from fastapi.testclient import TestClient
from nova_file_api.app import create_app


def test_openapi_contains_only_canonical_v1_routes() -> None:
    """OpenAPI should expose only canonical v1 and metrics routes."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200

    payload = response.json()
    paths = payload.get("paths", {})
    assert isinstance(paths, dict)

    expected_paths = {
        "/metrics/summary",
        "/v1/transfers/uploads/initiate",
        "/v1/transfers/uploads/sign-parts",
        "/v1/transfers/uploads/complete",
        "/v1/transfers/uploads/abort",
        "/v1/transfers/downloads/presign",
        "/v1/jobs",
        "/v1/jobs/{job_id}",
        "/v1/jobs/{job_id}/cancel",
        "/v1/jobs/{job_id}/retry",
        "/v1/jobs/{job_id}/events",
        "/v1/internal/jobs/{job_id}/result",
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


def test_legacy_routes_are_not_exposed() -> None:
    """Legacy API and legacy health routes must remain removed."""
    app = create_app()
    with TestClient(app) as client:
        assert (
            client.post("/api/transfers/uploads/initiate", json={}).status_code
            == 404
        )
        assert client.post("/api/jobs/enqueue", json={}).status_code == 404
        assert client.get("/healthz").status_code == 404
        assert client.get("/readyz").status_code == 404
