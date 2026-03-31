"""Workflow-centric contract docs tests for the reduced release surface."""

from __future__ import annotations

import json
from typing import Any, cast

import yaml

from .helpers import REPO_ROOT, read_repo_file as _read


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
    """Kept workflow/release schema files must exist and parse cleanly."""
    for rel_path in [
        "docs/contracts/release-artifacts-v1.schema.json",
        "docs/contracts/deploy-output-authority-v2.schema.json",
        "docs/contracts/workflow-deploy-runtime-v1.schema.json",
        "docs/contracts/workflow-post-deploy-validate.schema.json",
        "docs/contracts/workflow-auth0-tenant-deploy.schema.json",
        "docs/contracts/workflow-auth0-tenant-ops-v1.schema.json",
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


def test_release_artifact_schema_contract_covers_required_gate_payloads() -> (
    None
):
    """Release artifact schema must cover staged publish and validation."""
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


def test_post_deploy_validate_schema_matches_reusable_workflow() -> None:
    """The post-deploy schema must match the reusable workflow API."""
    schema = _read_json(
        "docs/contracts/workflow-post-deploy-validate.schema.json"
    )
    workflow_call = _load_workflow_call(
        ".github/workflows/reusable-post-deploy-validate.yml"
    )

    workflow_inputs = workflow_call["inputs"]
    workflow_outputs = workflow_call["outputs"]
    schema_inputs = schema["properties"]["inputs"]["properties"]
    schema_outputs = schema["properties"]["outputs"]["properties"]
    workflow_required_inputs = {
        key
        for key, value in workflow_inputs.items()
        if value.get("required", False)
    }
    schema_required_inputs = set(
        schema["properties"]["inputs"].get("required", [])
    )

    assert set(workflow_inputs) == set(schema_inputs)
    assert set(workflow_outputs) == set(schema_outputs)
    assert workflow_required_inputs == schema_required_inputs
    assert schema_inputs["validation_cors_preflight_path"]["pattern"] == (
        "^/[^,\\s]+$"
    )


def test_deploy_runtime_schema_matches_reusable_workflow() -> None:
    """The deploy-runtime schema must match the reusable workflow API."""
    schema = _read_json("docs/contracts/workflow-deploy-runtime-v1.schema.json")
    workflow_call = _load_workflow_call(
        ".github/workflows/reusable-deploy-runtime.yml"
    )

    workflow_inputs = workflow_call["inputs"]
    workflow_outputs = workflow_call["outputs"]
    schema_inputs = schema["properties"]["inputs"]["properties"]
    schema_outputs = schema["properties"]["outputs"]["properties"]
    workflow_required_inputs = {
        key
        for key, value in workflow_inputs.items()
        if value.get("required", False)
    }
    schema_required_inputs = set(
        schema["properties"]["inputs"].get("required", [])
    )

    assert set(workflow_inputs) == set(schema_inputs)
    assert set(workflow_outputs) == set(schema_outputs)
    assert workflow_required_inputs == schema_required_inputs


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
        assert "deploy_repo: 3M-Cloud/nova" in text
        assert "deploy_run_id: ${{ inputs.nova_deploy_run_id }}" in text


def test_integration_guide_references_surviving_contract_docs() -> None:
    """The integration guide should point at surviving post-deploy contracts."""
    text = _read("docs/clients/post-deploy-validation-integration-guide.md")

    for required in [
        "reusable-post-deploy-validate.yml",
        "docs/contracts/deploy-output-authority-v2.schema.json",
        "docs/contracts/workflow-deploy-runtime-v1.schema.json",
        "docs/contracts/workflow-post-deploy-validate.schema.json",
        "docs/contracts/browser-live-validation-report.schema.json",
        "docs/contracts/release-artifacts-v1.schema.json",
        "docs/runbooks/release/release-policy.md",
        "Prefer a full commit SHA",
        "5-minute setup flow",
        "validation_protected_paths",
        "validation_cors_preflight_path",
        "validation_cors_origin",
        "/v1/releases/info",
        "/v1/health/live",
        "/v1/health/ready",
        "`execute-api` endpoint returns `403`",
        "401` or `403`",
        "CORS preflight",
    ]:
        assert required in text

    for forbidden in [
        "reusable-workflow-inputs-v1.schema.json",
        "reusable-workflow-outputs-v1.schema.json",
        "deploy-size-profiles-v1.json",
        "ssm-runtime-base-url-v1.schema.json",
        "ADR-0023-hard-cut-v1-canonical-route-surface.md",
        "requirements-wave-2.md",
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
    workflow_required_inputs = {
        key
        for key, value in workflow_inputs.items()
        if value.get("required", False)
    }
    schema_required_inputs = set(
        schema["properties"]["inputs"].get("required", [])
    )

    assert set(workflow_inputs) == set(schema_inputs)
    assert set(workflow_outputs) == set(schema_outputs)
    assert workflow_required_inputs == schema_required_inputs
