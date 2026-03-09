"""OpenAPI contract regression tests for auth API route stability."""

from __future__ import annotations

from typing import Any

from fastapi.routing import APIRoute
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
    expected_operation_map = {
        "/v1/health/live": {"get": "health_live"},
        "/v1/health/ready": {"get": "health_ready"},
        "/v1/token/verify": {"post": "verify_token"},
        "/v1/token/introspect": {
            "post": "introspect_token",
        },
    }
    assert _operation_id_map(payload) == expected_operation_map


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
    assert components["TokenIntrospectFormRequest"]["title"] == (
        "TokenIntrospectFormRequest"
    )


def test_openapi_schema_generation_smoke() -> None:
    """OpenAPI schema should build via app factory without exceptions."""
    app = create_app()
    schema = app.openapi()
    assert isinstance(schema, dict)
    assert schema.get("openapi") == "3.1.0"


def test_openapi_uses_canonical_error_response_components_only() -> None:
    """Auth OpenAPI should not expose FastAPI validation schemas."""
    app = create_app()
    schema = app.openapi()

    components = schema["components"]
    schemas = components["schemas"]
    responses = components["responses"]

    assert "HTTPValidationError" not in schemas
    assert "ValidationError" not in schemas
    assert "AuthInvalidRequestResponse" in responses
    assert schema["paths"]["/v1/token/verify"]["post"]["responses"]["422"] == {
        "$ref": "#/components/responses/AuthInvalidRequestResponse"
    }
    assert schema["paths"]["/v1/token/introspect"]["post"]["responses"][
        "401"
    ] == {"$ref": "#/components/responses/AuthUnauthorizedResponse"}
    assert schema["paths"]["/v1/token/introspect"]["post"]["responses"][
        "403"
    ] == {"$ref": "#/components/responses/AuthForbiddenResponse"}
    assert schema["paths"]["/v1/token/introspect"]["post"]["responses"][
        "422"
    ] == {"$ref": "#/components/responses/AuthInvalidRequestResponse"}
    assert schema["paths"]["/v1/health/ready"]["get"]["responses"]["503"] == {
        "$ref": "#/components/responses/AuthServiceUnavailableResponse"
    }
