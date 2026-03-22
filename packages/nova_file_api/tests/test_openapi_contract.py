"""OpenAPI contract regression tests for route cutover and schema build."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from fastapi import FastAPI
from fastapi.routing import APIRoute
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.auth import Authenticator
from nova_file_api.config import Settings
from nova_file_api.jobs import (
    JobService,
    MemoryJobPublisher,
    MemoryJobRepository,
)
from nova_file_api.metrics import MetricsCollector

from .support.app import (
    build_cache_stack,
    build_runtime_deps,
    build_test_app,
)
from .support.doubles import StubTransferService

_HTTP_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
)
_EXPECTED_OPERATION_ID_MAP = {
    "/metrics/summary": {"get": "metrics_summary"},
    "/v1/transfers/uploads/initiate": {"post": "initiate_upload"},
    "/v1/transfers/uploads/sign-parts": {"post": "sign_upload_parts"},
    "/v1/transfers/uploads/introspect": {"post": "introspect_upload"},
    "/v1/transfers/uploads/complete": {"post": "complete_upload"},
    "/v1/transfers/uploads/abort": {"post": "abort_upload"},
    "/v1/transfers/downloads/presign": {"post": "presign_download"},
    "/v1/jobs": {"get": "list_jobs", "post": "create_job"},
    "/v1/jobs/{job_id}": {"get": "get_job_status"},
    "/v1/jobs/{job_id}/cancel": {"post": "cancel_job"},
    "/v1/jobs/{job_id}/retry": {"post": "retry_job"},
    "/v1/jobs/{job_id}/events": {"get": "list_job_events"},
    "/v1/capabilities": {"get": "get_capabilities"},
    "/v1/resources/plan": {"post": "plan_resources"},
    "/v1/releases/info": {"get": "get_release_info"},
    "/v1/health/live": {"get": "health_live"},
    "/v1/health/ready": {"get": "health_ready"},
}


def _string_object_mapping(value: object) -> Mapping[str, object]:
    assert isinstance(value, Mapping)
    assert all(isinstance(key, str) for key in value)
    return cast(Mapping[str, object], value)


def _string_list(value: object) -> list[str]:
    assert isinstance(value, list)
    assert all(isinstance(item, str) for item in value)
    return cast(list[str], value)


def _schema_operation_id_map(
    payload: dict[str, object],
) -> dict[str, dict[str, str]]:
    paths = _string_object_mapping(payload.get("paths", {}))

    operation_map: dict[str, dict[str, str]] = {}
    for path, path_item in paths.items():
        path_mapping = _string_object_mapping(path_item)
        method_ids: dict[str, str] = {}
        for method, operation in path_mapping.items():
            if method not in _HTTP_METHODS:
                continue
            operation_mapping = _string_object_mapping(operation)
            operation_id = operation_mapping.get("operationId")
            assert isinstance(operation_id, str)
            assert operation_id
            method_ids[method] = operation_id
        if method_ids:
            operation_map[path] = method_ids
    return operation_map


def _route_operation_id_map(app: FastAPI) -> dict[str, dict[str, str]]:
    route_map: dict[str, dict[str, str]] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        assert isinstance(route.operation_id, str)
        assert route.operation_id
        for method in route.methods:
            normalized_method = method.lower()
            if normalized_method not in _HTTP_METHODS:
                continue
            route_map.setdefault(route.path, {})[normalized_method] = (
                route.operation_id
            )
    return route_map


def _build_openapi_app() -> FastAPI:
    """Build the file API app without real external dependencies."""
    settings = Settings()
    settings.jobs_enabled = True

    metrics = MetricsCollector(namespace="Tests")
    shared, cache = build_cache_stack()
    repository = MemoryJobRepository()
    return build_test_app(
        build_runtime_deps(
            settings=settings,
            metrics=metrics,
            shared_cache=shared,
            cache=cache,
            authenticator=Authenticator(settings=settings, cache=cache),
            transfer_service=StubTransferService(),
            job_service=JobService(
                repository=repository,
                publisher=MemoryJobPublisher(),
                metrics=metrics,
            ),
            activity_store=MemoryActivityStore(),
            idempotency_enabled=True,
            use_in_memory_shared_cache=True,
        )
    )


def _operation_tag_map(
    payload: dict[str, object],
) -> dict[str, dict[str, list[str]]]:
    paths = _string_object_mapping(payload.get("paths", {}))

    operation_map: dict[str, dict[str, list[str]]] = {}
    for path, path_item in paths.items():
        path_mapping = _string_object_mapping(path_item)
        method_tags: dict[str, list[str]] = {}
        for method, operation in path_mapping.items():
            if method not in _HTTP_METHODS:
                continue
            operation_mapping = _string_object_mapping(operation)
            operation_id = operation_mapping.get("operationId")
            raw_tags = operation_mapping.get("tags")
            assert raw_tags is not None, (
                f"operation tags missing for {method.upper()} {path}"
                f" (operationId={operation_id!r})"
            )
            tags = _string_list(raw_tags)
            method_tags[method] = tags
        if method_tags:
            operation_map[path] = method_tags
    return operation_map


def test_openapi_path_method_operation_ids_match_routes() -> None:
    """OpenAPI should expose the same operation ids declared on routes."""
    app = _build_openapi_app()
    payload = app.openapi()
    assert _schema_operation_id_map(payload) == _EXPECTED_OPERATION_ID_MAP
    assert _route_operation_id_map(app) == _EXPECTED_OPERATION_ID_MAP


def test_openapi_path_method_tags_are_semantic() -> None:
    """OpenAPI should group file API operations under semantic tags."""
    app = _build_openapi_app()
    payload = app.openapi()
    expected_tag_map = {
        "/metrics/summary": {"get": ["ops"]},
        "/v1/transfers/uploads/initiate": {"post": ["transfers"]},
        "/v1/transfers/uploads/sign-parts": {"post": ["transfers"]},
        "/v1/transfers/uploads/introspect": {"post": ["transfers"]},
        "/v1/transfers/uploads/complete": {"post": ["transfers"]},
        "/v1/transfers/uploads/abort": {"post": ["transfers"]},
        "/v1/transfers/downloads/presign": {"post": ["transfers"]},
        "/v1/jobs": {"get": ["jobs"], "post": ["jobs"]},
        "/v1/jobs/{job_id}": {"get": ["jobs"]},
        "/v1/jobs/{job_id}/cancel": {"post": ["jobs"]},
        "/v1/jobs/{job_id}/retry": {"post": ["jobs"]},
        "/v1/jobs/{job_id}/events": {"get": ["jobs"]},
        "/v1/capabilities": {"get": ["platform"]},
        "/v1/resources/plan": {"post": ["platform"]},
        "/v1/releases/info": {"get": ["platform"]},
        "/v1/health/live": {"get": ["ops"]},
        "/v1/health/ready": {"get": ["ops"]},
    }
    assert _operation_tag_map(payload) == expected_tag_map


def test_route_operation_ids_are_present_and_unique() -> None:
    """Application routes should expose non-empty, unique operation ids."""
    app = _build_openapi_app()
    operation_ids = [
        route.operation_id
        for route in app.routes
        if isinstance(route, APIRoute) and route.include_in_schema
    ]
    assert operation_ids
    assert all(
        isinstance(operation_id, str) and operation_id
        for operation_id in operation_ids
    )
    assert len(operation_ids) == len(set(operation_ids))


def test_openapi_schema_generation_smoke() -> None:
    """OpenAPI schema should build via app factory without exceptions."""
    app = _build_openapi_app()
    schema = app.openapi()
    assert isinstance(schema, dict)
    assert schema.get("openapi") == "3.1.0"


def test_openapi_route_declared_error_contracts() -> None:
    """OpenAPI should expose route-declared error and readiness responses."""
    app = _build_openapi_app()
    payload = app.openapi()

    jobs_post = payload["paths"]["/v1/jobs"]["post"]["responses"]
    assert jobs_post["409"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorEnvelope"
    }
    assert jobs_post["409"]["description"] == (
        "Conflict - Idempotency request is already in progress."
    )
    assert jobs_post["503"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorEnvelope"
    }
    assert jobs_post["503"]["description"] == (
        "Service Unavailable - Queue publishing or idempotency storage is "
        "unavailable."
    )
    assert jobs_post["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorEnvelope"
    }

    transfer_initiate_post = payload["paths"]["/v1/transfers/uploads/initiate"][
        "post"
    ]["responses"]
    for status_code in ("401", "403", "409", "422", "503"):
        assert transfer_initiate_post[status_code]["content"][
            "application/json"
        ]["schema"] == {"$ref": "#/components/schemas/ErrorEnvelope"}

    metrics_summary_get = payload["paths"]["/metrics/summary"]["get"][
        "responses"
    ]
    for status_code in ("401", "403"):
        assert metrics_summary_get[status_code]["content"]["application/json"][
            "schema"
        ] == {"$ref": "#/components/schemas/ErrorEnvelope"}

    plan_resources_post = payload["paths"]["/v1/resources/plan"]["post"][
        "responses"
    ]
    assert plan_resources_post["422"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ErrorEnvelope"}

    retry_job_post = payload["paths"]["/v1/jobs/{job_id}/retry"]["post"][
        "responses"
    ]
    for status_code in ("401", "403", "422"):
        assert retry_job_post[status_code]["content"]["application/json"][
            "schema"
        ] == {"$ref": "#/components/schemas/ErrorEnvelope"}

    ready_responses = payload["paths"]["/v1/health/ready"]["get"]["responses"]
    assert ready_responses["503"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ReadinessResponse"
    }
    assert ready_responses["503"]["description"] == (
        "Service Unavailable - Readiness failed."
    )

    components = payload["components"]
    assert "responses" not in components
    assert "HTTPValidationError" not in components["schemas"]
    assert "ValidationError" not in components["schemas"]


def test_openapi_error_envelope_schema_preserves_semantic_fields() -> None:
    """ErrorEnvelope compatibility is defined by wire fields."""
    app = _build_openapi_app()
    payload = app.openapi()

    schemas = payload["components"]["schemas"]
    error_envelope = schemas["ErrorEnvelope"]
    error_schema = error_envelope["properties"]["error"]
    if "$ref" in error_schema:
        schema_name = error_schema["$ref"].rsplit("/", 1)[-1]
        error_schema = schemas[schema_name]

    assert error_schema["type"] == "object"
    assert error_schema["additionalProperties"] is False
    assert set(error_schema["required"]) == {
        "code",
        "message",
        "details",
        "request_id",
    }
    assert error_schema["properties"]["code"]["type"] == "string"
    assert error_schema["properties"]["message"]["type"] == "string"
    assert error_schema["properties"]["details"]["type"] == "object"
    request_id_schema = error_schema["properties"]["request_id"]
    assert sorted(item["type"] for item in request_id_schema["anyOf"]) == [
        "null",
        "string",
    ]


def test_openapi_uses_bearer_security_for_public_routes() -> None:
    """Public OpenAPI routes advertise bearer auth."""
    app = _build_openapi_app()
    payload = app.openapi()

    security_schemes = payload["components"]["securitySchemes"]
    assert "bearerAuth" in security_schemes
    assert "sessionAuth" not in security_schemes
    assert "X-Worker-Token" not in security_schemes
    assert security_schemes["bearerAuth"]["type"] == "http"
    assert security_schemes["bearerAuth"]["scheme"] == "bearer"
    assert security_schemes["bearerAuth"]["bearerFormat"] == "JWT"

    public_post = payload["paths"]["/v1/jobs"]["post"]
    assert public_post["security"] == [{"bearerAuth": []}]


def test_legacy_routes_are_not_exposed() -> None:
    """Legacy API and legacy health routes must remain removed."""
    app = _build_openapi_app()
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/api/transfers/uploads/initiate" not in route_paths
    assert "/api/jobs/enqueue" not in route_paths
    assert "/healthz" not in route_paths
