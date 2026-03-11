"""OpenAPI contract regression tests for route cutover and schema build."""

from __future__ import annotations

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
from nova_file_api.models import AuthMode
from nova_file_api.operation_ids import OPERATION_ID_BY_PATH_AND_METHOD

from .support.app import (
    build_cache_stack,
    build_runtime_deps,
    build_test_app,
)
from .support.doubles import StubTransferService

_HTTP_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
)


def _build_openapi_app() -> FastAPI:
    """Build the file API app without real external dependencies."""
    settings = Settings()
    settings.auth_mode = AuthMode.SAME_ORIGIN
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
        )
    )


def _operation_id_map(
    payload: dict[str, object],
) -> dict[str, dict[str, str]]:
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
    payload: dict[str, object],
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
    app = _build_openapi_app()
    payload = app.openapi()
    assert _operation_id_map(payload) == OPERATION_ID_BY_PATH_AND_METHOD


def test_openapi_path_method_tags_are_semantic() -> None:
    """OpenAPI should group file API operations under semantic tags."""
    app = _build_openapi_app()
    payload = app.openapi()
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


def test_routes_cover_the_explicit_operation_id_contract() -> None:
    """Application routes should match the explicit operation-id contract."""
    app = _build_openapi_app()
    route_map: dict[str, dict[str, str]] = {}
    operation_ids = [
        route.operation_id
        for route in app.routes
        if isinstance(route, APIRoute) and route.include_in_schema
    ]
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        assert isinstance(route.operation_id, str)
        expected_methods = OPERATION_ID_BY_PATH_AND_METHOD.get(route.path)
        if expected_methods is None:
            continue
        for method in route.methods:
            normalized_method = method.lower()
            if (
                normalized_method not in _HTTP_METHODS
                or normalized_method not in expected_methods
            ):
                continue
            route_map.setdefault(route.path, {})[normalized_method] = (
                route.operation_id
            )
    assert operation_ids
    assert all(
        isinstance(operation_id, str) and operation_id
        for operation_id in operation_ids
    )
    assert route_map == OPERATION_ID_BY_PATH_AND_METHOD
    assert len(operation_ids) == len(set(operation_ids))


def test_openapi_schema_generation_smoke() -> None:
    """OpenAPI schema should build via app factory without exceptions."""
    app = _build_openapi_app()
    schema = app.openapi()
    assert isinstance(schema, dict)
    assert schema.get("openapi") == "3.1.0"


def test_openapi_customized_error_and_visibility_contracts() -> None:
    """OpenAPI should retain error, readiness, and visibility wiring."""
    app = _build_openapi_app()
    payload = app.openapi()

    jobs_post = payload["paths"]["/v1/jobs"]["post"]["responses"]
    assert jobs_post["409"] == {
        "$ref": "#/components/responses/FileIdempotencyConflictResponse"
    }
    assert jobs_post["503"] == {
        "$ref": "#/components/responses/FileQueueUnavailableResponse"
    }

    ready_responses = payload["paths"]["/v1/health/ready"]["get"]["responses"]
    assert ready_responses["503"]["description"] == (
        "Service Unavailable - Readiness failed"
    )

    worker_post = payload["paths"]["/v1/internal/jobs/{job_id}/result"]["post"]
    assert worker_post["x-nova-sdk-visibility"] == "internal"
    assert worker_post["security"] == [{"X-Worker-Token": []}]


def test_legacy_routes_are_not_exposed() -> None:
    """Legacy API and legacy health routes must remain removed."""
    app = _build_openapi_app()
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/api/transfers/uploads/initiate" not in route_paths
    assert "/api/jobs/enqueue" not in route_paths
    assert "/healthz" not in route_paths
