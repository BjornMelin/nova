"""Tests for release client catalog generation helpers."""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.release.r_sdk import (
    _render_r_client,
    _render_r_description,
    _render_r_license_text,
    _render_r_namespace,
    _render_r_package_manual,
)
from scripts.release.sdk_common import (
    TARGETS,
    GenerationTarget,
    Operation,
    OperationParameter,
    _assert_unique_operation_ids,
    _build_public_openapi_spec,
    _default_operation_id,
    _load_operations,
)
from scripts.release.typescript_sdk import (
    _COMPAT_GET_PARSE_AS_SIGNATURE,
    _UPSTREAM_GET_PARSE_AS_SIGNATURE,
    _apply_typescript_upstream_compatibility_fixes,
    _check_typescript_generated_output,
    _run_openapi_ts,
)


def test_default_operation_id_keeps_path_parameter_names() -> None:
    """Verify default operation IDs preserve path-parameter names."""
    assert (
        _default_operation_id(
            method="get",
            path="/v1/examples/{example_id}/events",
        )
        == "get_v1_examples_by_example_id_events"
    )


def test_assert_unique_operation_ids_fails_on_collision() -> None:
    """Verify duplicate operation IDs raise a ValueError."""
    with pytest.raises(ValueError, match="Duplicate operationId"):
        _assert_unique_operation_ids(
            spec_path=Path("spec.json"),
            operations=[
                Operation(
                    operation_id="example_lookup",
                    method="GET",
                    path="/v1/examples/{example_id}",
                    summary=None,
                    has_request_body=False,
                    has_required_request_body=False,
                    path_parameters=(
                        OperationParameter("example_id", required=True),
                    ),
                    query_parameters=(),
                    has_header_params=False,
                    has_required_header_params=False,
                    request_content_types=(),
                    response_status_codes=(200,),
                ),
                Operation(
                    operation_id="example_lookup",
                    method="GET",
                    path="/v1/examples/{other_id}",
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


def test_repo_spec_public_operations_follow_exports_first_contract() -> None:
    """The committed public spec must stay aligned to the exports-first API."""
    spec_path = (
        Path(__file__).resolve().parents[3]
        / "packages"
        / "contracts"
        / "openapi"
        / "nova-file-api.openapi.json"
    )
    _, operations = _load_operations(spec_path)
    operation_ids = {operation.operation_id for operation in operations}
    public_paths = {operation.path for operation in operations}
    assert {
        "list_exports",
        "create_export",
        "get_export",
        "cancel_export",
    } <= operation_ids
    assert all("/v1/jobs" not in path for path in public_paths)
    assert all("job" not in operation_id for operation_id in operation_ids)


def test_request_body_ref_requiredness_is_preserved_for_r_generation(
    tmp_path: Path,
) -> None:
    """Optional requestBody refs still drive requiredness metadata."""
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

    required = by_id["post_required"]
    assert required.has_request_body is True
    assert required.has_required_request_body is True


def test_load_operations_excludes_internal_visibility_operations(
    tmp_path: Path,
) -> None:
    """TypeScript/R catalogs should ignore internal-only operations."""
    spec_path = tmp_path / "spec.openapi.json"
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/v1/exports": {
                "post": {
                    "operationId": "create_export",
                    "requestBody": {
                        "$ref": "#/components/requestBodies/PublicExportBody"
                    },
                    "responses": {
                        "201": {
                            "description": "created",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": (
                                            "#/components/schemas/ExportResource"
                                        )
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/internal/reconcile": {
                "post": {
                    "operationId": "reconcile_internal",
                    "x-nova-sdk-visibility": "internal",
                    "requestBody": {
                        "$ref": "#/components/requestBodies/InternalOnlyBody"
                    },
                    "responses": {
                        "202": {
                            "description": "accepted",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": (
                                            "#/components/schemas/InternalOnlyResponse"
                                        )
                                    }
                                }
                            },
                        }
                    },
                }
            },
        },
        "components": {
            "requestBodies": {
                "PublicExportBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": (
                                    "#/components/schemas/CreateExportRequest"
                                )
                            }
                        }
                    },
                },
                "InternalOnlyBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": (
                                    "#/components/schemas/InternalOnlyRequest"
                                )
                            }
                        }
                    },
                },
            },
            "schemas": {
                "CreateExportRequest": {
                    "type": "object",
                    "properties": {"source_key": {"type": "string"}},
                    "required": ["source_key"],
                },
                "ExportResource": {
                    "type": "object",
                    "properties": {"export_id": {"type": "string"}},
                    "required": ["export_id"],
                },
                "InternalOnlyRequest": {
                    "type": "object",
                    "properties": {"worker_id": {"type": "string"}},
                    "required": ["worker_id"],
                },
                "InternalOnlyResponse": {
                    "type": "object",
                    "properties": {"accepted": {"type": "boolean"}},
                    "required": ["accepted"],
                },
            },
        },
    }
    spec_path.write_text(
        json.dumps(spec),
        encoding="utf-8",
    )

    loaded_spec, operations = _load_operations(spec_path)

    assert [operation.operation_id for operation in operations] == [
        "create_export"
    ]
    public_spec = _build_public_openapi_spec(loaded_spec)
    public_paths = public_spec.get("paths", {})
    assert isinstance(public_paths, dict)
    assert set(public_paths) == {"/v1/exports"}
    public_components = public_spec.get("components", {})
    assert isinstance(public_components, dict)
    public_request_bodies = public_components.get("requestBodies", {})
    assert isinstance(public_request_bodies, dict)
    public_schemas = public_components.get("schemas", {})
    assert isinstance(public_schemas, dict)
    assert "PublicExportBody" in public_request_bodies
    assert "InternalOnlyBody" not in public_request_bodies
    assert "CreateExportRequest" in public_schemas
    assert "ExportResource" in public_schemas
    assert "InternalOnlyRequest" not in public_schemas
    assert "InternalOnlyResponse" not in public_schemas


def test_check_typescript_generated_output_flags_drift_and_legacy_files(
    tmp_path: Path,
) -> None:
    """Check-mode should fail on drift and leftover legacy TS files."""
    expected_root = tmp_path / "expected"
    actual_package_root = tmp_path / "package"
    (expected_root / "core").mkdir(parents=True)
    (actual_package_root / "src" / "client" / "core").mkdir(parents=True)
    (expected_root / "sdk.gen.ts").write_text("// fresh", encoding="utf-8")
    (expected_root / "core" / "utils.gen.ts").write_text(
        "// missing",
        encoding="utf-8",
    )
    (actual_package_root / "src" / "client" / "sdk.gen.ts").write_text(
        "// stale",
        encoding="utf-8",
    )
    (actual_package_root / "src" / "client.ts").write_text(
        "// legacy",
        encoding="utf-8",
    )

    issues = _check_typescript_generated_output(
        actual_package_root,
        expected_root=expected_root,
    )

    assert issues
    assert any(
        "missing expected generated SDK artifacts" in issue for issue in issues
    )
    assert any("sdk.gen.ts" in issue for issue in issues)
    assert any(
        "obsolete TypeScript SDK artifact still present" in issue
        for issue in issues
    )


def test_typescript_compatibility_fix_allows_undefined_parse_as(
    tmp_path: Path,
) -> None:
    """Generated TS output keeps the required Nova parseAs compatibility."""
    generated_root = tmp_path / "client"
    utils_path = generated_root / "client" / "utils.gen.ts"
    utils_path.parent.mkdir(parents=True)
    utils_path.write_text(
        (
            "export const getParseAs = (contentType: string | null): "
            "Exclude<Config['parseAs'], 'auto'> => {\n"
            "  return;\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    _apply_typescript_upstream_compatibility_fixes(generated_root)

    source = utils_path.read_text(encoding="utf-8")
    assert "Exclude<Config['parseAs'], 'auto'> | undefined" in source
    assert _UPSTREAM_GET_PARSE_AS_SIGNATURE not in source
    assert _COMPAT_GET_PARSE_AS_SIGNATURE in source


def test_run_openapi_ts_times_out_with_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeouts from @hey-api/openapi-ts include explicit error context."""
    monkeypatch.setattr(
        "scripts.release.typescript_sdk.OPENAPI_TS_CLI",
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
        _run_openapi_ts(
            input_spec_path=Path("spec.openapi.json"),
            output_path=Path("generated"),
        )


def test_run_openapi_ts_requires_repo_installed_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing local CLI should fail with an npm bootstrap hint."""
    monkeypatch.setattr(
        "scripts.release.typescript_sdk.OPENAPI_TS_CLI",
        Path(__file__).with_name("missing-openapi-ts"),
    )

    with pytest.raises(RuntimeError, match="run `npm ci` from repo root"):
        _run_openapi_ts(
            input_spec_path=Path("spec.openapi.json"),
            output_path=Path("generated"),
        )


@pytest.mark.parametrize("target", TARGETS)
def test_render_r_description_includes_valid_maintainer_metadata(
    target: GenerationTarget,
) -> None:
    """R DESCRIPTION metadata must match the generator-owned contract."""
    description = _render_r_description(target)

    expected_maintainer = (
        'Authors@R: person("Nova SDK Team", email = "sdk@nova.invalid", '
        'role = c("aut", "cre"))'
    )
    assert expected_maintainer in description
    assert "License: file LICENSE" in description
    assert "RoxygenNote: 7.3.3" in description
    assert "    testthat (>= 3.2.3)," in description
    assert "    withr (>= 3.0.2)" in description


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
