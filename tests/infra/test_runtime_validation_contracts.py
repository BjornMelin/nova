"""Runtime validation and runtime-config truth contracts."""

from __future__ import annotations

import json

from .helpers import (
    load_repo_module,
    load_repo_package_module,
    read_repo_file as _read,
)
from .test_runtime_stack_contracts import _build_bundle, _resources_of_type

_VALIDATOR = load_repo_module(
    "validate_runtime_release",
    "scripts/release/validate_runtime_release.py",
)
_MANIFEST = load_repo_package_module(
    "nova_cdk.runtime_release_manifest",
    "infra/nova_cdk/src",
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
    assert '"name": "enable_waf"' in json.dumps(payload["deploy_inputs"])
    assert "enable_waf" in markdown
    assert "Service template environment contract" not in markdown
    assert "Worker template environment contract" not in markdown
    assert "FILE_TRANSFER_UPLOAD_SESSIONS_TABLE" in markdown
    assert "FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY" in markdown
    assert "FILE_TRANSFER_POLICY_VERSION" in markdown
    assert "FILE_TRANSFER_RESUMABLE_WINDOW_SECONDS" in markdown
    assert "BLOCKING_IO_THREAD_TOKENS" not in json.dumps(payload)
    assert "BLOCKING_IO_THREAD_TOKENS" not in markdown


def test_runtime_contract_literal_env_matches_synthesized_stack() -> None:
    """Generated runtime contracts must match the synthesized stack surface."""
    payload = json.loads(
        _read("packages/contracts/fixtures/runtime_config_contract.json")
    )
    bundle = _build_bundle()
    api_env = bundle.api_function_env
    functions = _resources_of_type(bundle.resources, "AWS::Lambda::Function")
    workflow_env = next(
        resource["Properties"]["Environment"]["Variables"]
        for resource in functions.values()
        if resource["Properties"]["Handler"]
        == "nova_workflows.handlers.copy_export_handler"
    )
    api_contract_names = {
        entry["name"] for entry in payload["api_lambda_environment"]["env"]
    }
    workflow_contract_names = {
        entry["name"] for entry in payload["workflow_task_environment"]["env"]
    }

    assert set(api_env) == api_contract_names
    assert set(workflow_env) == workflow_contract_names

    for entry in payload["api_lambda_environment"]["env"]:
        if entry["value"] is None:
            continue
        assert api_env[entry["name"]] == entry["value"]

    for entry in payload["workflow_task_environment"]["env"]:
        if entry["value"] is None:
            continue
        assert workflow_env[entry["name"]] == entry["value"]

    expected_copy_concurrency = _MANIFEST.default_export_copy_max_concurrency(2)
    assert api_env["FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY"] == str(
        expected_copy_concurrency
    )
    assert workflow_env["FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY"] == str(
        expected_copy_concurrency
    )


def test_runtime_contract_handlers_match_authority_and_validator() -> None:
    """Contract handlers and validator prefixes must share authority."""
    payload = json.loads(
        _read("packages/contracts/fixtures/runtime_config_contract.json")
    )
    bundle = _build_bundle()
    functions = _resources_of_type(bundle.resources, "AWS::Lambda::Function")
    expected_handlers = set(_MANIFEST.workflow_handler_names())
    actual_handlers = {
        resource["Properties"]["Handler"]
        for resource in functions.values()
        if resource["Properties"]["Handler"].startswith(
            "nova_workflows.handlers."
        )
    }

    assert tuple(payload["workflow_task_environment"]["handlers"]) == (
        _MANIFEST.workflow_handler_names()
    )
    assert (
        _MANIFEST.function_logical_id_prefixes()
    ) == _VALIDATOR._FUNCTION_LOGICAL_ID_PREFIXES
    assert expected_handlers <= actual_handlers


def test_runtime_validation_reserved_concurrency_defaults_share_authority() -> (
    None
):
    """Validator concurrency expectations must come from shared authority."""
    assert _VALIDATOR._expected_reserved_concurrency(
        environment_name="dev",
        account_concurrency_limit=1000,
    ) == _MANIFEST.expected_runtime_reserved_concurrency(
        environment_name="dev",
        account_concurrency_limit=1000,
    )
    assert _VALIDATOR._expected_reserved_concurrency(
        environment_name="dev",
        account_concurrency_limit=999,
    ) == _MANIFEST.expected_runtime_reserved_concurrency(
        environment_name="dev",
        account_concurrency_limit=999,
    )
    assert _VALIDATOR._expected_reserved_concurrency(
        environment_name="prod",
        account_concurrency_limit=999,
    ) == _MANIFEST.expected_runtime_reserved_concurrency(
        environment_name="prod",
        account_concurrency_limit=999,
    )
