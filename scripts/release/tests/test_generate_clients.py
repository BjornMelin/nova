"""Tests for release client catalog generation helpers."""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.release.generate_clients import (
    TARGETS,
    GenerationTarget,
    Operation,
    OperationParameter,
    _assert_unique_operation_ids,
    _collect_public_schema_names,
    _default_operation_id,
    _load_operations,
    _render_r_client,
    _render_r_description,
    _render_r_license_text,
    _render_r_namespace,
    _render_r_package_manual,
    _render_typescript_openapi,
    _validate_generated_directory,
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
                    path_parameters=(
                        OperationParameter("job_id", required=True),
                    ),
                    query_parameters=(),
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
                    path_parameters=(
                        OperationParameter("other_id", required=True),
                    ),
                    query_parameters=(),
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


def test_load_operations_excludes_internal_visibility_operations(
    tmp_path: Path,
) -> None:
    """TypeScript/R catalogs should ignore internal-only operations."""
    spec_path = tmp_path / "spec.openapi.json"
    spec_path.write_text(
        json.dumps(
            {
                "openapi": "3.1.0",
                "paths": {
                    "/v1/public": {
                        "get": {
                            "operationId": "get_public",
                            "responses": {"200": {"description": "ok"}},
                        }
                    },
                    "/v1/internal": {
                        "post": {
                            "operationId": "post_internal",
                            "x-nova-sdk-visibility": "internal",
                            "responses": {"202": {"description": "accepted"}},
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    _, operations = _load_operations(spec_path)

    assert [operation.operation_id for operation in operations] == [
        "get_public"
    ]


def test_validate_generated_directory_flags_non_empty_directory(
    tmp_path: Path,
) -> None:
    """Check-mode should fail when required artifacts are missing."""
    generated_dir = tmp_path / "src" / "generated"
    generated_dir.mkdir(parents=True)
    stale_file = generated_dir / "stale.ts"
    stale_file.write_text("// stale", encoding="utf-8")

    issues = _validate_generated_directory(tmp_path, check=True)

    assert issues
    assert "missing expected generated SDK artifacts" in issues[0]
    assert "openapi.ts" in issues[0]
    assert any("stale.ts" in issue or "unexpected" in issue for issue in issues)


def test_render_typescript_openapi_times_out_with_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeouts from openapi-typescript include explicit error context."""
    monkeypatch.setattr(
        "scripts.release.generate_clients.OPENAPI_TYPESCRIPT_CLI",
        Path(__file__),
    )

    def _raise_timeout(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(
            cmd=[str(Path(__file__))],
            timeout=120,
            output="stdout details",
            stderr="stderr details",
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        _raise_timeout,
    )

    with pytest.raises(RuntimeError, match="timed out after 120s"):
        _render_typescript_openapi(Path("spec.openapi.json"))


def test_render_typescript_openapi_requires_repo_installed_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing local CLI should fail with an npm bootstrap hint."""
    monkeypatch.setattr(
        "scripts.release.generate_clients.OPENAPI_TYPESCRIPT_CLI",
        Path(__file__).with_name("missing-openapi-typescript"),
    )

    with pytest.raises(RuntimeError, match="run `npm ci` from repo root"):
        _render_typescript_openapi(Path("spec.openapi.json"))


@pytest.mark.parametrize("target", TARGETS)
def test_render_r_description_includes_valid_maintainer_metadata(
    target: GenerationTarget,
) -> None:
    """R DESCRIPTION metadata must include a named maintainer with email."""
    description = _render_r_description(target)

    expected_maintainer = (
        'Authors@R: person("Nova SDK Team", email = "sdk@nova.invalid", '
        'role = c("aut", "cre"))'
    )
    assert expected_maintainer in description
    assert "License: file LICENSE" in description


@pytest.mark.parametrize("target", TARGETS)
def test_render_r_description_preserves_existing_version(
    target: GenerationTarget, tmp_path: Path
) -> None:
    """Regeneration should preserve an existing release-bumped DESCRIPTION."""
    package_root = tmp_path / target.r_output_path.parent.parent.name
    package_root.mkdir(parents=True)
    (package_root / "DESCRIPTION").write_text(
        "\n".join(
            [
                f"Package: {target.r_package_name}",
                "Type: Package",
                f"Title: {target.r_package_title}",
                "Version: 9.9.9",
                (
                    'Authors@R: person("Nova SDK Team", email = '
                    '"sdk@nova.invalid", role = c("aut", "cre"))'
                ),
                f"Description: {target.r_package_description}",
                "License: file LICENSE",
                "",
            ]
        ),
        encoding="utf-8",
    )
    preserved_target = replace(
        target,
        r_output_path=package_root / "R" / "generated.R",
        r_client_output_path=package_root / "R" / "client.R",
    )

    description = _render_r_description(preserved_target)

    assert "Version: 9.9.9" in description


@pytest.mark.parametrize("target", TARGETS)
def test_render_r_license_text_marks_package_internal(
    target: GenerationTarget,
) -> None:
    """Generated R package license text should reflect internal-only use."""
    license_text = _render_r_license_text(target)

    assert target.r_package_title in license_text
    assert "internal Nova use only" in license_text


@pytest.mark.parametrize("target", TARGETS)
def test_render_r_client_defaults_default_headers_to_null(
    target: GenerationTarget,
) -> None:
    """Generated R constructors must accept omitted default headers."""
    client_code = _render_r_client(target)

    assert "default_headers = NULL" in client_code
    assert "request_descriptor" not in client_code
    assert "execute_operation" not in client_code
    assert "bearer_token_env" in client_code
    assert "request_performer" not in client_code
    assert "req_body_json" in client_code
    assert "content_type = NULL" not in client_code
    assert "request_content_types = character(0)" not in client_code
    assert "normalize_user_agent" in client_code
    assert "response = cnd$resp" in client_code
    assert "parent = class(cnd)" in client_code
    assert (
        'any(tolower(names(request_headers)) == "authorization")' in client_code
    )
    assert (
        "duplicated(tolower(names(merged_headers)), fromLast = TRUE)"
        in client_code
    )


@pytest.mark.parametrize("target", TARGETS)
def test_render_r_namespace_registers_nova_error_formatter(
    target: GenerationTarget,
) -> None:
    """Generated R namespaces must register the Nova error S3 formatter."""
    namespace = _render_r_namespace(target)
    expected_error_class = f"{target.r_client_prefix}_api_error"

    assert f"S3method(conditionMessage,{expected_error_class})" in namespace


@pytest.mark.parametrize("target", TARGETS)
def test_render_r_package_manual_documents_usage_arguments(
    target: GenerationTarget,
) -> None:
    """Generated R package manuals must document every usage argument."""
    manual = _render_r_package_manual(target)
    _, operations = _load_operations(target.spec_path)

    for argument_name in (
        "base_url",
        "bearer_token",
        "bearer_token_env",
        "default_headers",
        "timeout_seconds",
        "user_agent",
        "token",
        "env_var",
    ):
        assert f"\\item{{{argument_name}}}" in manual
    assert f'"{target.r_client_prefix.upper()}_BEARER_TOKEN"' in manual
    for operation in operations:
        assert (
            f"\\section{{{target.r_client_prefix}_{operation.operation_id}}}"
            in manual
        )
