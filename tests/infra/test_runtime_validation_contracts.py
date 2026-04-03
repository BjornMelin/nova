"""Runtime validation and runtime-config truth contracts."""

from __future__ import annotations

import json

from .helpers import load_repo_module, read_repo_file as _read

_VALIDATOR = load_repo_module(
    "validate_runtime_release",
    "scripts/release/validate_runtime_release.py",
)


def test_runtime_validation_defaults_target_public_and_protected_truth() -> (
    None
):
    """Validation defaults should reflect public and protected truth."""
    assert _VALIDATOR.DEFAULT_CANONICAL == (
        "/v1/health/live",
        "/v1/health/ready",
        "/v1/capabilities",
        "/v1/releases/info",
    )
    assert _VALIDATOR.DEFAULT_PROTECTED == (
        "GET /metrics/summary",
        "POST /v1/exports",
    )
    assert _VALIDATOR.DEFAULT_CORS_PREFLIGHT_PATH == "/v1/exports"


def test_runtime_config_contract_artifacts_drop_deleted_template_surfaces() -> (
    None
):
    """Generated artifacts should describe live Lambda surfaces."""
    payload = json.loads(
        _read("packages/contracts/fixtures/runtime_config_contract.json")
    )
    markdown = _read("docs/contracts/runtime-config-contract.generated.md")

    assert "deploy_inputs" in payload
    assert "api_lambda_environment" in payload
    assert "workflow_task_environment" in payload
    assert "service_template" not in payload
    assert "worker_template" not in payload

    assert "## Runtime deploy inputs" in markdown
    assert "## API Lambda environment contract" in markdown
    assert "## Workflow task Lambda environment contract" in markdown
    assert "Service template environment contract" not in markdown
    assert "Worker template environment contract" not in markdown
