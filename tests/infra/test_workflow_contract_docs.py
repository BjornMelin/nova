"""Workflow-centric contract docs tests for WS6/WS8 artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _read_json(rel: str) -> dict[str, Any]:
    return json.loads(_read(rel))


def _load_workflow_call(rel: str) -> dict[str, Any]:
    workflow = yaml.safe_load(_read(rel))
    on_cfg = workflow.get("on")
    if on_cfg is None:
        on_cfg = workflow.get(True)
    assert isinstance(on_cfg, dict)
    call_cfg = on_cfg.get("workflow_call")
    assert isinstance(call_cfg, dict)
    return call_cfg


def test_contract_schema_files_exist_and_are_valid_json() -> None:
    """Contract schema files must exist and parse as JSON objects."""
    for rel_path in [
        "docs/contracts/reusable-workflow-inputs-v1.schema.json",
        "docs/contracts/reusable-workflow-outputs-v1.schema.json",
        "docs/contracts/deploy-size-profiles-v1.json",
        "docs/contracts/release-artifacts-v1.schema.json",
        "docs/contracts/workflow-post-deploy-validate.schema.json",
        "docs/contracts/workflow-auth0-tenant-deploy.schema.json",
        "docs/contracts/ssm-runtime-base-url-v1.schema.json",
        "docs/contracts/browser-live-validation-report.schema.json",
    ]:
        path = REPO_ROOT / rel_path
        assert path.is_file(), f"Missing contract schema file: {rel_path}"
        data = _read_json(rel_path)
        assert isinstance(data, dict)
        if rel_path.endswith(".schema.json"):
            assert (
                data.get("$schema")
                == "https://json-schema.org/draft/2020-12/schema"
            )
            assert "$id" in data
            assert data.get("type") == "object"
        else:
            assert data.get("schema_version") == "1.0"

    assert not (
        REPO_ROOT / "docs/contracts/workflow-auth0-tenant-ops-v1.schema.json"
    ).exists()


def test_auth0_and_ssm_contract_schemas_include_required_keys() -> None:
    """Auth0 and SSM contract schemas must expose required authority fields."""
    auth0_schema = _read_json(
        "docs/contracts/workflow-auth0-tenant-deploy.schema.json"
    )
    ssm_schema = _read_json(
        "docs/contracts/ssm-runtime-base-url-v1.schema.json"
    )

    assert set(auth0_schema["required"]) == {"inputs", "outputs"}
    auth0_inputs = auth0_schema["properties"]["inputs"]["properties"]
    assert auth0_inputs["mode"]["enum"] == ["validate", "import", "export"]
    assert auth0_inputs["allow_delete"]["const"] is False

    assert {"schema_version", "service_name", "dev", "prod"} == set(
        ssm_schema["required"]
    )
    assert (
        ssm_schema["$defs"]["base_url_binding"]["properties"]["parameter_path"][
            "pattern"
        ]
        == "^/nova/(dev|prod)/[A-Za-z0-9_.-]+/base-url$"
    )


def test_workflow_io_schema_contract_matches_reusable_deploy_runtime_api() -> (
    None
):
    """Workflow schema must codify reusable deploy-runtime API."""
    input_schema = _read_json(
        "docs/contracts/reusable-workflow-inputs-v1.schema.json"
    )
    output_schema = _read_json(
        "docs/contracts/reusable-workflow-outputs-v1.schema.json"
    )
    workflow_call = _load_workflow_call(
        ".github/workflows/reusable-deploy-runtime.yml"
    )
    workflow_inputs = workflow_call["inputs"]
    workflow_outputs = workflow_call["outputs"]

    schema_inputs = input_schema["properties"]
    schema_outputs = output_schema["properties"]

    assert set(workflow_inputs).issubset(set(schema_inputs))
    assert set(workflow_outputs) == set(schema_outputs)

    for required_input in input_schema["required"]:
        assert required_input in workflow_inputs
        assert workflow_inputs[required_input].get("required") is True

    assert (
        output_schema["properties"]["manifest_sha256"]["pattern"]
        == "^[a-f0-9]{64}$"
    )


def test_release_artifact_schema_contract_covers_required_gate_payloads() -> (
    None
):
    """Release artifacts schema must include gate and post-deploy payloads."""
    schema = _read_json("docs/contracts/release-artifacts-v1.schema.json")
    props = schema["properties"]
    defs = schema["$defs"]

    for key in [
        "changed_units",
        "version_plan",
        "codeartifact_gate_report",
        "codeartifact_promotion_candidates",
        "post_deploy_validation_report",
        "browser_live_validation_report",
    ]:
        assert key in props

    for required_def in [
        "changed_units",
        "version_plan",
        "codeartifact_gate_report",
        "promotion_candidate",
        "post_deploy_validation_report",
        "route_check",
        "browser_live_validation_report",
    ]:
        assert required_def in defs

    workspace_unit_props = defs["workspace_unit_ref"]["properties"]
    assert workspace_unit_props["format"]["enum"] == ["pypi", "npm"]
    assert defs["promotion_candidate"]["properties"]["format"]["enum"] == [
        "pypi",
        "npm",
    ]


def test_size_profiles_schema_contract_covers_dash_rshiny_react_next() -> None:
    """Size-profile schema must include required downstream consumer lanes."""
    schema = _read_json("docs/contracts/deploy-size-profiles-v1.json")
    profile_props = schema["profiles"]

    for lane in ["dash", "rshiny", "react-next"]:
        assert lane in profile_props

    lane_def = profile_props["dash"]
    for tier in ["small", "medium", "large"]:
        assert tier in lane_def


def test_downstream_examples_reference_reusable_post_deploy_workflow() -> None:
    """Downstream examples must call the shared reusable workflow."""
    workflow_ref = (
        "uses: 3M-Cloud/nova/.github/workflows/"
        "reusable-post-deploy-validate.yml@v1.x.y"
    )
    for rel_path in [
        "docs/clients/examples/workflows/dash-post-deploy-validate.yml",
        "docs/clients/examples/workflows/rshiny-post-deploy-validate.yml",
        "docs/clients/examples/workflows/react-next-post-deploy-validate.yml",
    ]:
        text = _read(rel_path)
        assert workflow_ref in text
        assert "validation_base_url: ${{ vars.NOVA_API_BASE_URL }}" in text
        assert "validation_canonical_paths:" in text
        assert "validation_legacy_404_paths:" in text


def test_downstream_minimal_workflow_files_exist_and_pin_release_tag() -> None:
    """Minimal downstream workflow examples must pin immutable release tags."""
    for rel_path in [
        "docs/clients/dash-minimal-workflow.yml",
        "docs/clients/rshiny-minimal-workflow.yml",
        "docs/clients/react-next-minimal-workflow.yml",
    ]:
        text = _read(rel_path)
        assert "reusable-post-deploy-validate.yml@v1.x.y" in text
        assert "validation_base_url: ${{ vars.NOVA_API_BASE_URL }}" in text


def test_integration_guide_includes_major_and_immutable_ref_guidance() -> None:
    """Integration guide must document major-tag and immutable-pin policy."""
    text = _read("docs/clients/post-deploy-validation-integration-guide.md")

    for required in [
        "reusable-post-deploy-validate.yml",
        "docs/contracts/workflow-post-deploy-validate.schema.json",
        "docs/contracts/workflow-auth0-tenant-deploy.schema.json",
        "docs/contracts/browser-live-validation-report.schema.json",
        "docs/contracts/release-artifacts-v1.schema.json",
        "docs/contracts/reusable-workflow-inputs-v1.schema.json",
        "docs/contracts/reusable-workflow-outputs-v1.schema.json",
        "docs/contracts/deploy-size-profiles-v1.json",
        "@v1",
        "@v1.x.y",
        "full commit SHA",
        (
            "Branch refs such as `@main` are not part of the supported "
            "consumer contract."
        ),
    ]:
        assert required in text

    for forbidden in [
        "latest-only prelaunch",
        "exact commit SHA before use",
    ]:
        assert forbidden not in text


def test_auth0_workflow_schema_matches_reusable_auth0_api() -> None:
    """Auth0 workflow schema must align with reusable workflow_call contract."""
    schema = _read_json(
        "docs/contracts/workflow-auth0-tenant-deploy.schema.json"
    )
    workflow_call = _load_workflow_call(
        ".github/workflows/reusable-auth0-tenant-deploy.yml"
    )

    workflow_inputs = workflow_call["inputs"]
    workflow_outputs = workflow_call["outputs"]
    schema_inputs = schema["properties"]["inputs"]["properties"]
    schema_outputs = schema["properties"]["outputs"]["properties"]

    assert set(workflow_inputs).issubset(set(schema_inputs))
    assert set(workflow_outputs).issubset(set(schema_outputs))

    for required_input in schema["properties"]["inputs"]["required"]:
        assert required_input in workflow_inputs
