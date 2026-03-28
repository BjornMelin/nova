"""Workflow-centric contract docs tests for WS6/WS8 artifacts."""

from __future__ import annotations

import json
from typing import Any, cast

import yaml

from .helpers import REPO_ROOT
from .helpers import read_repo_file as _read


def _read_json(rel: str) -> dict[str, Any]:
    payload = json.loads(_read(rel))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


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
        "docs/contracts/workflow-auth0-tenant-ops-v1.schema.json",
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


def test_auth0_and_ssm_contract_schemas_include_required_keys() -> None:
    """Auth0 and SSM contract schemas must expose required authority fields."""
    auth0_schema = _read_json(
        "docs/contracts/workflow-auth0-tenant-ops-v1.schema.json"
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
    deploy_runtime_output_schema = output_schema["$defs"][
        "deploy_runtime_output"
    ]
    schema_outputs = deploy_runtime_output_schema["properties"]

    assert set(workflow_inputs).issubset(set(schema_inputs))
    assert set(workflow_outputs) == set(schema_outputs)
    assert set(deploy_runtime_output_schema["required"]) == set(
        workflow_outputs
    )
    assert "image_digest" in schema_inputs
    assert "image_tag" not in schema_inputs

    for required_input in input_schema["required"]:
        assert required_input in workflow_inputs
        assert workflow_inputs[required_input].get("required") is True

    assert (
        output_schema["$defs"]["manifest_sha256"]["pattern"] == "^[a-f0-9]{64}$"
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
        "promotion_input_digests",
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
    assert workspace_unit_props["format"]["enum"] == ["pypi", "npm", "r"]
    assert workspace_unit_props["codeartifact_format"]["enum"] == [
        "pypi",
        "npm",
        "generic",
    ]
    changed_units_items = defs["changed_units"]["properties"]["changed_units"][
        "items"
    ]
    changed_unit_item_props = changed_units_items["properties"]
    version_plan_item_props = defs["version_plan"]["properties"]["units"][
        "items"
    ]["properties"]
    assert changed_unit_item_props["format"]["enum"] == [
        "pypi",
        "npm",
        "r",
    ]
    assert changed_unit_item_props["codeartifact_format"]["enum"] == [
        "pypi",
        "npm",
        "generic",
    ]
    assert changed_unit_item_props["namespace"]["type"] == ["string", "null"]
    assert version_plan_item_props["format"]["enum"] == [
        "pypi",
        "npm",
        "r",
    ]
    assert version_plan_item_props["codeartifact_format"]["enum"] == [
        "pypi",
        "npm",
        "generic",
    ]
    assert version_plan_item_props["namespace"]["type"] == ["string", "null"]
    promotion_candidate_def = defs["promotion_candidate"]
    assert promotion_candidate_def["properties"]["format"]["enum"] == [
        "pypi",
        "npm",
        "r",
    ]
    assert promotion_candidate_def["properties"]["codeartifact_format"][
        "enum"
    ] == ["pypi", "npm", "generic"]
    assert promotion_candidate_def["properties"]["namespace"]["pattern"] == (
        "^[a-z0-9][a-z0-9-]*$"
    )
    assert promotion_candidate_def["properties"]["unit_id"]["type"] == "string"
    assert promotion_candidate_def["properties"]["unit_id"]["minLength"] == 1
    assert (
        promotion_candidate_def["properties"]["tarball_sha256"]["$ref"]
        == "#/$defs/sha256_digest"
    )
    assert (
        promotion_candidate_def["properties"]["signature_sha256"]["$ref"]
        == "#/$defs/sha256_digest"
    )
    assert (
        schema["properties"]["codeartifact_promotion_candidates"]["uniqueItems"]
        is True
    )
    npm_condition = next(
        entry["then"]["properties"]
        for entry in promotion_candidate_def["allOf"]
        if entry.get("if", {})
        .get("properties", {})
        .get("format", {})
        .get("const")
        == "npm"
    )
    assert npm_condition["namespace"]["const"] == "nova"
    assert npm_condition["package"]["pattern"] == "^@nova/[a-z0-9][a-z0-9-]*$"
    r_condition = next(
        entry["then"]
        for entry in promotion_candidate_def["allOf"]
        if entry.get("if", {})
        .get("properties", {})
        .get("format", {})
        .get("const")
        == "r"
    )
    assert r_condition["required"] == [
        "tarball_sha256",
        "signature_sha256",
    ]
    r_props = r_condition["properties"]
    assert r_props["codeartifact_format"]["const"] == "generic"
    assert r_props["namespace"]["const"] == "nova"
    assert r_props["package"]["pattern"] == ("^[a-z0-9][a-z0-9._-]{0,254}$")
    assert r_props["tarball_sha256"]["$ref"] == "#/$defs/sha256_digest"
    assert r_props["signature_sha256"]["$ref"] == "#/$defs/sha256_digest"


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
        "reusable-post-deploy-validate.yml@"
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


def test_downstream_minimal_workflow_files_exist_and_use_immutable_pin() -> (
    None
):
    """Minimal downstream workflow examples must use immutable workflow pins."""
    for rel_path in [
        "docs/clients/dash-minimal-workflow.yml",
        "docs/clients/rshiny-minimal-workflow.yml",
        "docs/clients/react-next-minimal-workflow.yml",
    ]:
        text = _read(rel_path)
        assert (
            "reusable-post-deploy-validate.yml"
            "@655ccab0d071c828045de4a4d3bb441d4349194e"
        ) in text
        assert "validation_base_url: ${{ vars.NOVA_API_BASE_URL }}" in text


def test_integration_guide_includes_versioning_policy_references() -> None:
    """Integration guide must reference release and versioning docs."""
    text = _read("docs/clients/post-deploy-validation-integration-guide.md")

    for required in [
        "reusable-post-deploy-validate.yml",
        "docs/contracts/workflow-post-deploy-validate.schema.json",
        "docs/contracts/workflow-auth0-tenant-deploy.schema.json",
        "docs/contracts/browser-live-validation-report.schema.json",
        "docs/contracts/release-artifacts-v1.schema.json",
        "docs/contracts/reusable-workflow-inputs-v1.schema.json",
        (
            "docs/contracts/reusable-workflow-outputs-v1.schema.json"
            "#/$defs/validation_report_output"
        ),
        "docs/contracts/deploy-size-profiles-v1.json",
        "docs/runbooks/release/release-policy.md",
        (
            "docs/architecture/spec/"
            "SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md"
        ),
        "655ccab0d071c828045de4a4d3bb441d4349194e",
        "Prefer a full commit SHA",
        "5-minute setup flow",
    ]:
        assert required in text


def test_governance_runbook_tracks_unified_required_checks() -> None:
    """Governance runbook must track the hosted required-check surface."""
    text = _read(
        "docs/runbooks/release/governance-lock-and-branch-protection.md"
    )

    for required in [
        "repository ruleset",
        "Nova CI",
        ".github/workflows/ci.yml",
        "quality-gates",
        "pytest-runtime-gates",
        "pytest-primary",
        "pytest-generated-smoke",
        "pytest-compatibility-3.11",
        "pytest-compatibility-3.12",
        "python-compatibility",
        "generated-clients",
        "dash-conformance",
        "shiny-conformance",
        "typescript-conformance",
        "cfn-and-contracts",
    ]:
        assert required in text

    for required in [
        "Do not require:",
        "classify-changes",
        "typescript-core-packages",
        "typescript-sdk-smoke",
    ]:
        assert required in text

    assert "conformance-clients.yml" not in text


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
