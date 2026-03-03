"""OpenAPI contract regression tests for auth API route stability."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from nova_auth_api.app import create_app

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
    """OpenAPI should expose stable auth path+method+operationId mappings."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200

    payload = response.json()
    expected_operation_map = {
        "/v1/health/live": {"get": "health_live_v1_health_live_get"},
        "/v1/token/verify": {"post": "verify_token_v1_token_verify_post"},
        "/v1/token/introspect": {
            "post": "introspect_token_v1_token_introspect_post",
        },
    }
    assert _operation_id_map(payload) == expected_operation_map


def test_openapi_schema_generation_smoke() -> None:
    """OpenAPI schema should build via app factory without exceptions."""
    app = create_app()
    schema = app.openapi()
    assert isinstance(schema, dict)
    assert schema.get("openapi") == "3.1.0"
