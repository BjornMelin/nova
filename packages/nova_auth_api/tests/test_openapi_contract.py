"""OpenAPI contract regression tests for auth API route stability."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from nova_auth_api.app import create_app
from nova_auth_api.operation_ids import OPERATION_ID_BY_PATH_AND_METHOD

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
    """OpenAPI should expose stable auth path+method+operationId mappings."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200

    payload = response.json()
    assert _operation_id_map(payload) == OPERATION_ID_BY_PATH_AND_METHOD


def test_openapi_path_method_tags_are_semantic() -> None:
    """OpenAPI should group auth operations under semantic tags."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200

    payload = response.json()
    expected_tag_map = {
        "/v1/health/live": {"get": ["health"]},
        "/v1/health/ready": {"get": ["health"]},
        "/v1/token/verify": {"post": ["token"]},
        "/v1/token/introspect": {"post": ["token"]},
    }
    assert _operation_tag_map(payload) == expected_tag_map


def test_routes_cover_the_explicit_operation_id_contract() -> None:
    """Application routes should match the explicit operation-id contract."""
    app = create_app()
    operation_ids: list[str] = []
    route_map: dict[str, dict[str, str]] = {}

    for route in app.routes:
        path = getattr(route, "path", None)
        operation_id = getattr(route, "operation_id", None)
        methods = getattr(route, "methods", None)
        include_in_schema = getattr(route, "include_in_schema", False)
        if not include_in_schema or not isinstance(path, str):
            continue
        assert isinstance(operation_id, str), (
            f"Route {path} missing operation_id"
        )
        assert isinstance(methods, set), (
            f"Route {path} missing methods: {methods!r}"
        )
        operation_ids.append(operation_id)
        expected_methods = OPERATION_ID_BY_PATH_AND_METHOD.get(path)
        if expected_methods is None:
            continue
        for method in methods:
            normalized_method = method.lower()
            if (
                normalized_method not in _HTTP_METHODS
                or normalized_method not in expected_methods
            ):
                continue
            route_map.setdefault(path, {})[normalized_method] = operation_id

    assert route_map == OPERATION_ID_BY_PATH_AND_METHOD
    assert len(operation_ids) == len(set(operation_ids))


def test_introspect_request_body_reuses_named_schema_for_all_media_types() -> (
    None
):
    """Introspection request body should use named component schemas only."""
    app = create_app()
    schema = app.openapi()
    request_body = schema["paths"]["/v1/token/introspect"]["post"][
        "requestBody"
    ]
    content = request_body["content"]
    assert content["application/json"]["schema"] == {
        "$ref": "#/components/schemas/TokenIntrospectRequest"
    }
    assert content["application/x-www-form-urlencoded"]["schema"] == {
        "$ref": "#/components/schemas/TokenIntrospectFormRequest"
    }
    components = schema["components"]["schemas"]
    assert components["TokenIntrospectRequest"]["title"] == (
        "TokenIntrospectRequest"
    )
    form_schema = components["TokenIntrospectFormRequest"]
    assert form_schema["title"] == "TokenIntrospectFormRequest"
    assert form_schema["required"] == ["token"]
    assert form_schema["properties"]["token"]["type"] == "string"
    assert form_schema["properties"]["token"]["minLength"] == 1
    assert form_schema["properties"]["token_type_hint"]["type"] == "string"
    assert "access_token" not in form_schema["properties"]


def test_openapi_schema_generation_smoke() -> None:
    """OpenAPI schema should build via app factory without exceptions."""
    app = create_app()
    schema = app.openapi()
    assert isinstance(schema, dict)
    assert schema.get("openapi") == "3.1.0"
