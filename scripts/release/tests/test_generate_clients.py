"""Tests for release client catalog generation helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.release.generate_clients import (
    Operation,
    _assert_unique_operation_ids,
    _collect_public_schema_names,
    _default_operation_id,
    _load_operations,
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
