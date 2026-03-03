"""OpenAPI contract regression tests for route cutover and schema build."""

from __future__ import annotations

from typing import Any

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


def test_openapi_path_method_operation_ids_are_stable() -> None:
    """OpenAPI should expose stable path+method+operationId mappings."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200

    payload = response.json()
    expected_operation_map = {
        "/metrics/summary": {
            "get": "metrics_summary_metrics_summary_get",
        },
        "/v1/transfers/uploads/initiate": {
            "post": "initiate_upload_v1_transfers_uploads_initiate_post",
        },
        "/v1/transfers/uploads/sign-parts": {
            "post": "sign_parts_v1_transfers_uploads_sign_parts_post",
        },
        "/v1/transfers/uploads/complete": {
            "post": "complete_upload_v1_transfers_uploads_complete_post",
        },
        "/v1/transfers/uploads/abort": {
            "post": "abort_upload_v1_transfers_uploads_abort_post",
        },
        "/v1/transfers/downloads/presign": {
            "post": "presign_download_v1_transfers_downloads_presign_post",
        },
        "/v1/jobs": {
            "get": "v1_list_jobs_v1_jobs_get",
            "post": "create_job_v1_jobs_post",
        },
        "/v1/jobs/{job_id}": {
            "get": "get_job_status_v1_jobs__job_id__get",
        },
        "/v1/jobs/{job_id}/cancel": {
            "post": "cancel_job_v1_jobs__job_id__cancel_post",
        },
        "/v1/jobs/{job_id}/retry": {
            "post": "v1_retry_job_v1_jobs__job_id__retry_post",
        },
        "/v1/jobs/{job_id}/events": {
            "get": "v1_job_events_v1_jobs__job_id__events_get",
        },
        "/v1/internal/jobs/{job_id}/result": {
            "post": "update_job_result_v1_internal_jobs__job_id__result_post",
        },
        "/v1/capabilities": {
            "get": "v1_capabilities_v1_capabilities_get",
        },
        "/v1/resources/plan": {
            "post": "v1_resources_plan_v1_resources_plan_post",
        },
        "/v1/releases/info": {
            "get": "v1_releases_info_v1_releases_info_get",
        },
        "/v1/health/live": {
            "get": "v1_health_live_v1_health_live_get",
        },
        "/v1/health/ready": {
            "get": "v1_health_ready_v1_health_ready_get",
        },
    }
    assert _operation_id_map(payload) == expected_operation_map


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
