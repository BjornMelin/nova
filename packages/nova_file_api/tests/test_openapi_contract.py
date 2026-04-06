"""OpenAPI contract regression tests for route cutover and schema build."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from fastapi import FastAPI
from fastapi.routing import APIRoute

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.config import Settings
from nova_file_api.exports import (
    ExportService,
    MemoryExportPublisher,
    MemoryExportRepository,
)
from nova_runtime_support.metrics import MetricsCollector

from .support.app import (
    build_cache_stack,
    build_runtime_deps,
    build_test_app,
)
from .support.doubles import StubAuthenticator, StubTransferService

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
    "/v1/exports": {"get": "list_exports", "post": "create_export"},
    "/v1/exports/{export_id}": {"get": "get_export"},
    "/v1/exports/{export_id}/cancel": {"post": "cancel_export"},
    "/v1/capabilities": {"get": "get_capabilities"},
    "/v1/capabilities/transfers": {"get": "get_transfer_capabilities"},
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
    settings = Settings.model_validate(
        {
            "EXPORTS_ENABLED": True,
            "IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency",
        }
    )

    metrics = MetricsCollector(namespace="Tests")
    cache = build_cache_stack()
    repository = MemoryExportRepository()
    return build_test_app(
        build_runtime_deps(
            settings=settings,
            metrics=metrics,
            cache=cache,
            authenticator=StubAuthenticator(),
            transfer_service=StubTransferService(),
            export_service=ExportService(
                repository=repository,
                publisher=MemoryExportPublisher(),
                metrics=metrics,
            ),
            activity_store=MemoryActivityStore(),
            idempotency_enabled=True,
        )
    )


def _build_openapi_app_with_stub_auth() -> FastAPI:
    """App matching OpenAPI tests, using stub bearer auth for HTTP checks."""
    settings = Settings.model_validate(
        {
            "EXPORTS_ENABLED": True,
            "IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency",
        }
    )

    metrics = MetricsCollector(namespace="Tests")
    cache = build_cache_stack()
    repository = MemoryExportRepository()
    return build_test_app(
        build_runtime_deps(
            settings=settings,
            metrics=metrics,
            cache=cache,
            authenticator=StubAuthenticator(),
            transfer_service=StubTransferService(),
            export_service=ExportService(
                repository=repository,
                publisher=MemoryExportPublisher(),
                metrics=metrics,
            ),
            activity_store=MemoryActivityStore(),
            idempotency_enabled=True,
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
        "/v1/exports": {"get": ["exports"], "post": ["exports"]},
        "/v1/exports/{export_id}": {"get": ["exports"]},
        "/v1/exports/{export_id}/cancel": {"post": ["exports"]},
        "/v1/capabilities": {"get": ["platform"]},
        "/v1/capabilities/transfers": {"get": ["platform"]},
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
    assert (
        schema["components"]["schemas"]["HTTPValidationError"]["properties"][
            "detail"
        ]["maxItems"]
        == 256
    )
    assert (
        schema["components"]["schemas"]["ValidationError"]["properties"]["loc"][
            "maxItems"
        ]
        == 32
    )
    assert (
        schema["components"]["schemas"]["HTTPValidationError"]["description"]
        == "Validation error envelope returned for invalid request payloads."
    )
    assert schema["components"]["schemas"]["ValidationError"][
        "description"
    ] == (
        "One request-validation issue with location, message, and error type."
    )
    assert schema["info"]["description"] == (
        "Typed control-plane API for direct-to-S3 uploads, presigned "
        "downloads, and durable export workflows.\n\n"
        "This API coordinates transfer policy discovery, multipart session "
        "state, and export workflow lifecycle metadata. It is not a bulk "
        "data-plane proxy; clients transfer object bytes directly with S3 "
        "using the returned metadata."
    )


def test_openapi_tag_descriptions_capture_runtime_domain_boundaries() -> None:
    """OpenAPI tags should describe the active public API surface areas."""
    app = _build_openapi_app()
    schema = app.openapi()
    tag_map = {
        tag["name"]: tag["description"]
        for tag in cast(list[dict[str, str]], schema["tags"])
    }

    assert tag_map == {
        "transfers": (
            "Direct-to-S3 upload and download planning endpoints, including "
            "multipart session orchestration."
        ),
        "exports": (
            "Durable export workflow resources used to create, inspect, list, "
            "and cancel caller-owned exports."
        ),
        "platform": (
            "Capability, release, and supportability endpoints that describe "
            "the current deployment contract."
        ),
        "ops": (
            "Operational liveness, readiness, and metrics endpoints for "
            "runtime health and observability."
        ),
    }


def test_openapi_declares_bearer_auth_scheme() -> None:
    """OpenAPI should keep the canonical bearer security scheme."""
    app = _build_openapi_app()
    schema = app.openapi()
    security_schemes = schema["components"]["securitySchemes"]
    bearer_auth = security_schemes["bearerAuth"]
    assert bearer_auth["type"] == "http"
    assert bearer_auth["scheme"] == "bearer"
    assert bearer_auth["bearerFormat"] == "JWT"


def test_openapi_route_declared_error_contracts() -> None:
    """OpenAPI should expose route-declared error and readiness responses."""
    app = _build_openapi_app()
    payload = app.openapi()

    exports_post = payload["paths"]["/v1/exports"]["post"]["responses"]
    assert exports_post["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ExportResource"
    }
    assert exports_post["201"]["description"] == (
        "Created export workflow resource."
    )
    assert exports_post["409"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorEnvelope"
    }
    assert exports_post["409"]["description"] == (
        "Conflict - Idempotency request is already in progress."
    )
    assert exports_post["503"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorEnvelope"
    }
    assert exports_post["503"]["description"] == (
        "Service Unavailable - Queue publishing or idempotency storage "
        "is unavailable."
    )

    transfer_caps = payload["paths"]["/v1/capabilities/transfers"]["get"]
    assert transfer_caps["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/TransferCapabilitiesResponse"}

    ready_responses = payload["paths"]["/v1/health/ready"]["get"]["responses"]
    assert ready_responses["503"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ReadinessResponse"
    }

    get_export_responses = payload["paths"]["/v1/exports/{export_id}"]["get"][
        "responses"
    ]
    assert get_export_responses["404"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ErrorEnvelope"}
    cancel_export_responses = payload["paths"][
        "/v1/exports/{export_id}/cancel"
    ]["post"]["responses"]
    assert cancel_export_responses["404"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ErrorEnvelope"}


def test_openapi_route_docs_use_explicit_summary_description_and_returns() -> (
    None
):
    """Public operations should publish explicit summary and return text."""
    app = _build_openapi_app()
    payload = app.openapi()

    initiate_upload = payload["paths"]["/v1/transfers/uploads/initiate"]["post"]
    assert (
        initiate_upload["summary"] == "Initiate a direct-to-S3 upload session"
    )
    assert initiate_upload["description"] == (
        "Resolve the effective transfer policy for the caller and return the "
        "presigned metadata needed to upload directly to S3."
    )
    assert initiate_upload["responses"]["200"]["description"] == (
        "Resolved upload session metadata, policy hints, and presigned inputs."
    )

    transfer_caps = payload["paths"]["/v1/capabilities/transfers"]["get"]
    assert transfer_caps["summary"] == "Get the effective transfer policy"
    assert transfer_caps["description"] == (
        "Expose the current transfer policy envelope that browser and native "
        "upload clients should honor."
    )
    assert transfer_caps["responses"]["200"]["description"] == (
        "Effective transfer policy metadata and limits."
    )


def test_openapi_parameters_and_schema_fields_expose_reference_docs() -> None:
    """OpenAPI should expose parameter and field descriptions for SDK refs."""
    app = _build_openapi_app()
    payload = app.openapi()

    create_export_headers = payload["paths"]["/v1/exports"]["post"][
        "parameters"
    ]
    assert create_export_headers[0]["name"] == "Idempotency-Key"
    assert create_export_headers[0]["description"] == (
        "Client-supplied idempotency key used to deduplicate supported "
        "mutation requests."
    )

    get_export_params = payload["paths"]["/v1/exports/{export_id}"]["get"][
        "parameters"
    ]
    assert get_export_params[0]["name"] == "export_id"
    assert get_export_params[0]["description"] == (
        "Identifier of the caller-owned export workflow resource."
    )

    list_exports_params = payload["paths"]["/v1/exports"]["get"]["parameters"]
    assert list_exports_params[0]["name"] == "limit"
    assert list_exports_params[0]["description"] == (
        "Maximum number of caller-owned export workflow resources to return, "
        "ordered newest first."
    )

    capability_params = payload["paths"]["/v1/capabilities/transfers"]["get"][
        "parameters"
    ]
    assert capability_params[0]["name"] == "workload_class"
    assert capability_params[0]["description"] == (
        "Optional workload-class hint used to resolve a narrower effective "
        "transfer policy."
    )

    export_resource = payload["components"]["schemas"]["ExportResource"][
        "properties"
    ]
    assert export_resource["export_id"]["description"] == (
        "Identifier of the caller-owned export workflow resource."
    )
    assert export_resource["status"]["description"] == (
        "Current lifecycle state of the export workflow."
    )

    initiate_upload_response = payload["components"]["schemas"][
        "InitiateUploadResponse"
    ]["properties"]
    assert initiate_upload_response["max_concurrency_hint"]["description"] == (
        "Suggested maximum number of concurrent client uploads."
    )
    assert initiate_upload_response["session_id"]["description"] == (
        "Durable upload-session identifier used for resume flows."
    )


def test_openapi_uses_bearer_security_scheme_only() -> None:
    """OpenAPI should expose only the native bearer security scheme."""
    app = _build_openapi_app()
    payload = app.openapi()

    security_schemes = payload["components"]["securitySchemes"]
    assert "bearerAuth" in security_schemes
    assert "sessionAuth" not in security_schemes
    assert security_schemes["bearerAuth"]["type"] == "http"
    assert security_schemes["bearerAuth"]["scheme"] == "bearer"


def test_legacy_job_routes_are_not_exposed() -> None:
    """The OpenAPI schema should no longer contain generic job routes."""
    app = _build_openapi_app_with_stub_auth()
    paths = app.openapi()["paths"]

    assert "/v1/jobs" not in paths
    assert "/v1/jobs/{job_id}" not in paths
    assert "/v1/jobs/{job_id}/retry" not in paths
    assert "/v1/jobs/{job_id}/events" not in paths
    assert "/v1/jobs/{job_id}/cancel" not in paths
