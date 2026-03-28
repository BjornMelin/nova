"""Workflow-centric contract docs tests for the reduced release surface."""

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
    """Kept workflow/release schema files must exist and parse cleanly."""
    for rel_path in [
        "docs/contracts/release-artifacts-v1.schema.json",
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

    assert set(workflow_inputs).issubset(set(schema_inputs))
    assert set(workflow_outputs).issubset(set(schema_outputs))


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


def test_integration_guide_references_surviving_contract_docs() -> None:
    """The integration guide should point at surviving post-deploy contracts."""
    text = _read("docs/clients/post-deploy-validation-integration-guide.md")

    for required in [
        "reusable-post-deploy-validate.yml",
        "docs/contracts/workflow-post-deploy-validate.schema.json",
        "docs/contracts/workflow-auth0-tenant-deploy.schema.json",
        "docs/contracts/browser-live-validation-report.schema.json",
        "docs/contracts/release-artifacts-v1.schema.json",
        "docs/runbooks/release/release-policy.md",
        "Prefer a full commit SHA",
        "5-minute setup flow",
    ]:
        assert required in text

    for forbidden in [
        "reusable-workflow-inputs-v1.schema.json",
        "reusable-workflow-outputs-v1.schema.json",
        "deploy-size-profiles-v1.json",
        "ssm-runtime-base-url-v1.schema.json",
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
