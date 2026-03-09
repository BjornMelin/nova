"""Tests for release client catalog generation helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.release import generate_clients as generate_clients_module
from scripts.release.generate_clients import (
    Operation,
    _assert_unique_operation_ids,
    _collect_public_schema_names,
    _default_operation_id,
    _load_operations,
    _remove_stale_generated_directory,
    _render_typescript_openapi,
)


def test_default_operation_id_keeps_path_parameter_names() -> None:
    """Verify default operation IDs preserve path-parameter names."""
    assert (
        _default_operation_id(
            method="get",
            path="/v1/jobs/{job_id}/events",
        )
        == "get_v1_jobs_by_job_id_events"
    )


def test_assert_unique_operation_ids_fails_on_collision() -> None:
    """Verify duplicate operation IDs raise a ValueError."""
    with pytest.raises(ValueError, match="Duplicate operationId"):
        _assert_unique_operation_ids(
            spec_path=Path("spec.json"),
            operations=[
                Operation(
                    operation_id="job_lookup",
                    method="GET",
                    path="/v1/jobs/{job_id}",
                    summary=None,
                    has_request_body=False,
                    has_required_request_body=False,
                    has_path_params=True,
                    has_query_params=False,
                    has_required_query_params=False,
                    has_header_params=False,
                    has_required_header_params=False,
                    request_content_types=(),
                    response_status_codes=(200,),
                ),
                Operation(
                    operation_id="job_lookup",
                    method="GET",
                    path="/v1/jobs/{other_id}",
                    summary=None,
                    has_request_body=False,
                    has_required_request_body=False,
                    has_path_params=True,
                    has_query_params=False,
                    has_required_query_params=False,
                    has_header_params=False,
                    has_required_header_params=False,
                    request_content_types=(),
                    response_status_codes=(200,),
                ),
            ],
        )


def test_public_schema_excludes_internal_job_result_shapes() -> None:
    """Public schema aliases exclude internal worker-only models."""
    spec_path = (
        Path(__file__).resolve().parents[3]
        / "packages"
        / "contracts"
        / "openapi"
        / "nova-file-api.openapi.json"
    )
    spec, operations = _load_operations(spec_path)

    schema_names = _collect_public_schema_names(spec, operations)

    assert "EnqueueJobRequest" in schema_names
    assert "JobResultUpdateRequest" not in schema_names
    assert "JobResultUpdateResponse" not in schema_names


def test_auth_introspection_collects_all_request_media_types() -> None:
    """Public auth operations keep all introspection media types."""
    spec_path = (
        Path(__file__).resolve().parents[3]
        / "packages"
        / "contracts"
        / "openapi"
        / "nova-auth-api.openapi.json"
    )
    _, operations = _load_operations(spec_path)

    introspect_operation = next(
        operation
        for operation in operations
        if operation.operation_id == "introspect_token"
    )

    assert introspect_operation.request_content_types == (
        "application/json",
        "application/x-www-form-urlencoded",
    )


def test_request_body_ref_requiredness_drives_method_request_signature(
    tmp_path: Path,
) -> None:
    """Optional requestBody refs stay optional, required refs stay required."""
    spec_path = tmp_path / "spec.openapi.json"
    spec_path.write_text(
        json.dumps(
            {
                "openapi": "3.1.0",
                "paths": {
                    "/v1/optional": {
                        "post": {
                            "operationId": "post_optional",
                            "requestBody": {
                                "$ref": (
                                    "#/components/requestBodies/OptionalBody"
                                )
                            },
                            "responses": {"200": {"description": "ok"}},
                        }
                    },
                    "/v1/required": {
                        "post": {
                            "operationId": "post_required",
                            "requestBody": {
                                "$ref": (
                                    "#/components/requestBodies/RequiredBody"
                                )
                            },
                            "responses": {"200": {"description": "ok"}},
                        }
                    },
                },
                "components": {
                    "requestBodies": {
                        "OptionalBody": {
                            "required": False,
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            },
                        },
                        "RequiredBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            },
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    _, operations = _load_operations(spec_path)
    by_id = {operation.operation_id: operation for operation in operations}

    optional = by_id["post_optional"]
    assert optional.has_request_body is True
    assert optional.has_required_request_body is False
    assert optional.requires_request is False

    required = by_id["post_required"]
    assert required.has_request_body is True
    assert required.has_required_request_body is True
    assert required.requires_request is True


def test_remove_stale_generated_directory_flags_non_empty_directory(
    tmp_path: Path,
) -> None:
    """Check-mode should fail when src/generated still has stale entries."""
    generated_dir = tmp_path / "src" / "generated"
    generated_dir.mkdir(parents=True)
    stale_file = generated_dir / "stale.ts"
    stale_file.write_text("// stale", encoding="utf-8")

    issues = _remove_stale_generated_directory(tmp_path, check=True)

    assert issues
    assert "non-empty" in issues[0]
    assert "stale.ts" in issues[0]


def test_render_typescript_openapi_times_out_with_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeouts from openapi-typescript include explicit error context."""

    def _raise_timeout(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(
            cmd=["npx", "--yes", "openapi-typescript@7.13.0"],
            timeout=120,
            output="stdout details",
            stderr="stderr details",
        )

    monkeypatch.setattr(
        generate_clients_module.subprocess,
        "run",
        _raise_timeout,
    )

    with pytest.raises(RuntimeError, match="timed out after 120s"):
        _render_typescript_openapi(Path("spec.openapi.json"))
