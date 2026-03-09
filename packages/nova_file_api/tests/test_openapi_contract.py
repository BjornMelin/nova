"""OpenAPI contract regression tests for route cutover and schema build."""

from __future__ import annotations

from typing import Any

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from nova_file_api.app import create_app

_HTTP_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
)


def _operation_id_map(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    paths = payload.get("paths", {})
    assert isinstance(paths, dict)

    operation_map: dict[str, dict[str, str]] = {}
    for path, path_item in paths.items():
        assert isinstance(path, str)
        assert isinstance(path_item, dict)
        method_ids: dict[str, str] = {}
        for method, operation in path_item.items():
            if method not in _HTTP_METHODS:
                continue
            assert isinstance(operation, dict)
            operation_id = operation.get("operationId")
            assert isinstance(operation_id, str)
            assert operation_id
            method_ids[method] = operation_id
        if method_ids:
            operation_map[path] = method_ids
    return operation_map


def _operation_tag_map(
    payload: dict[str, Any],
) -> dict[str, dict[str, list[str]]]:
    paths = payload.get("paths", {})
    assert isinstance(paths, dict)

    operation_map: dict[str, dict[str, list[str]]] = {}
    for path, path_item in paths.items():
        assert isinstance(path, str)
        assert isinstance(path_item, dict)
        method_tags: dict[str, list[str]] = {}
        for method, operation in path_item.items():
            if method not in _HTTP_METHODS:
                continue
            assert isinstance(operation, dict)
            tags = operation.get("tags")
            assert isinstance(tags, list)
            assert all(isinstance(tag, str) for tag in tags)
            method_tags[method] = tags
        if method_tags:
            operation_map[path] = method_tags
    return operation_map


def test_openapi_path_method_operation_ids_are_stable() -> None:
    """OpenAPI should expose stable path+method+operationId mappings."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200

    payload = response.json()
    expected_operation_map = {
        "/metrics/summary": {
            "get": "metrics_summary",
        },
        "/v1/transfers/uploads/initiate": {
            "post": "initiate_upload",
        },
        "/v1/transfers/uploads/sign-parts": {
            "post": "sign_upload_parts",
        },
        "/v1/transfers/uploads/complete": {
            "post": "complete_upload",
        },
        "/v1/transfers/uploads/abort": {
            "post": "abort_upload",
        },
        "/v1/transfers/downloads/presign": {
            "post": "presign_download",
        },
        "/v1/jobs": {
            "get": "list_jobs",
            "post": "create_job",
        },
        "/v1/jobs/{job_id}": {
            "get": "get_job_status",
        },
        "/v1/jobs/{job_id}/cancel": {
            "post": "cancel_job",
        },
        "/v1/jobs/{job_id}/retry": {
            "post": "retry_job",
        },
        "/v1/jobs/{job_id}/events": {
            "get": "list_job_events",
        },
        "/v1/internal/jobs/{job_id}/result": {
            "post": "update_job_result",
        },
        "/v1/capabilities": {
            "get": "get_capabilities",
        },
        "/v1/resources/plan": {
            "post": "plan_resources",
        },
        "/v1/releases/info": {
            "get": "get_release_info",
        },
        "/v1/health/live": {
            "get": "health_live",
        },
        "/v1/health/ready": {
            "get": "health_ready",
        },
    }
    assert _operation_id_map(payload) == expected_operation_map


def test_openapi_path_method_tags_are_semantic() -> None:
    """OpenAPI should group file API operations under semantic tags."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200

    payload = response.json()
    expected_tag_map = {
        "/metrics/summary": {"get": ["ops"]},
        "/v1/transfers/uploads/initiate": {"post": ["transfers"]},
        "/v1/transfers/uploads/sign-parts": {"post": ["transfers"]},
        "/v1/transfers/uploads/complete": {"post": ["transfers"]},
        "/v1/transfers/uploads/abort": {"post": ["transfers"]},
        "/v1/transfers/downloads/presign": {"post": ["transfers"]},
        "/v1/jobs": {"get": ["jobs"], "post": ["jobs"]},
        "/v1/jobs/{job_id}": {"get": ["jobs"]},
        "/v1/jobs/{job_id}/cancel": {"post": ["jobs"]},
        "/v1/jobs/{job_id}/retry": {"post": ["jobs"]},
        "/v1/jobs/{job_id}/events": {"get": ["jobs"]},
        "/v1/internal/jobs/{job_id}/result": {"post": ["jobs"]},
        "/v1/capabilities": {"get": ["platform"]},
        "/v1/resources/plan": {"post": ["platform"]},
        "/v1/releases/info": {"get": ["platform"]},
        "/v1/health/live": {"get": ["ops"]},
        "/v1/health/ready": {"get": ["ops"]},
    }
    assert _operation_tag_map(payload) == expected_tag_map


def test_route_names_are_unique_for_operation_ids() -> None:
    """Route names must remain unique when operationIds follow route names."""
    app = create_app()
    route_names = [
        route.name
        for route in app.routes
        if isinstance(route, APIRoute) and route.include_in_schema
    ]
    assert route_names
    assert len(route_names) == len(set(route_names))


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
