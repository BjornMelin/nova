"""Tests for the runtime config contract helper and env var naming."""

from __future__ import annotations

import pytest
from pydantic.fields import FieldInfo

from nova_file_api.config import Settings
from scripts.release.runtime_config_contract import (
    _env_var_name,
    build_contract_payload,
    runtime_setting_contracts,
)


def test_runtime_settings_define_explicit_string_validation_aliases() -> None:
    """Every runtime setting should declare one explicit env-var alias."""
    for field_name, field in Settings.model_fields.items():
        validation_alias = field.validation_alias
        assert isinstance(validation_alias, str), (
            f"{field_name} must use a string validation_alias"
        )
        assert validation_alias.strip(), (
            f"{field_name} validation_alias must be non-empty"
        )


def test_runtime_setting_contracts_use_validation_aliases() -> None:
    """Runtime contract env vars should come from validation_alias values."""
    contracts_by_field = {
        contract.field_name: contract
        for contract in runtime_setting_contracts()
    }

    for field_name, field in Settings.model_fields.items():
        validation_alias = field.validation_alias
        assert isinstance(validation_alias, str)
        assert contracts_by_field[field_name].env_var == validation_alias


def test_env_var_name_strips_validation_alias_whitespace() -> None:
    """Ensure validation_alias whitespace is stripped when deriving env vars."""
    field = FieldInfo(annotation=str, validation_alias="APP_NAME ")

    assert _env_var_name("app_name", field) == "APP_NAME"


def test_env_var_name_requires_explicit_validation_alias() -> None:
    """Verify a missing validation_alias raises ValueError."""
    field = FieldInfo(annotation=str)

    with pytest.raises(ValueError, match="must declare an explicit"):
        _env_var_name("app_name", field)


def test_step_functions_state_machine_arn_is_conditionally_required() -> None:
    """Step Functions runtime wiring should be reflected in the contract."""
    contracts_by_field = {
        contract.field_name: contract
        for contract in runtime_setting_contracts()
    }

    assert (
        contracts_by_field["export_workflow_state_machine_arn"].required_when
        == "when EXPORTS_ENABLED=true in the API Lambda"
    )


def test_runtime_contract_only_describes_living_lambda_surfaces() -> None:
    """Generated payload should not preserve deleted template contracts."""
    payload = build_contract_payload()

    assert "service_template" not in payload
    assert "worker_template" not in payload
    assert "deploy_inputs" in payload
    assert "api_lambda_environment" in payload
    assert "workflow_task_environment" in payload


def test_runtime_contract_tracks_api_release_digest_and_stepfunctions_env() -> (
    None
):
    """API Lambda env contract should include live deploy/runtime bindings."""
    payload = build_contract_payload()
    api_env = {
        entry["name"] for entry in payload["api_lambda_environment"]["env"]
    }
    workflow_env = {
        entry["name"] for entry in payload["workflow_task_environment"]["env"]
    }

    assert "API_RELEASE_ARTIFACT_SHA256" in api_env
    assert "EXPORT_WORKFLOW_STATE_MACHINE_ARN" in api_env
    assert "OIDC_ISSUER" in api_env
    assert "ALLOWED_ORIGINS" in api_env
    assert "FILE_TRANSFER_ACTIVE_MULTIPART_UPLOAD_LIMIT" in api_env
    assert "FILE_TRANSFER_DAILY_INGRESS_BUDGET_BYTES" in api_env
    assert "FILE_TRANSFER_SIGN_REQUESTS_PER_UPLOAD_LIMIT" in api_env
    assert "FILE_TRANSFER_STALE_MULTIPART_CLEANUP_AGE_SECONDS" not in api_env
    assert "FILE_TRANSFER_RECONCILIATION_SCAN_LIMIT" not in api_env
    assert "EXPORTS_ENABLED" in workflow_env
    assert "EXPORTS_DYNAMODB_TABLE" in workflow_env
    assert "EXPORT_WORKFLOW_STATE_MACHINE_ARN" not in workflow_env


def test_runtime_contract_type_labels_drop_annotated_validation_metadata() -> (
    None
):
    """Contract type labels should expose semantic types, not metadata."""
    contracts_by_field = {
        contract.field_name: contract
        for contract in runtime_setting_contracts()
    }

    assert contracts_by_field["file_transfer_bucket"].type_label == "str | None"
    assert contracts_by_field["oidc_issuer"].type_label == "str | None"


def test_runtime_contract_drops_deleted_blocking_io_setting() -> None:
    """Dead runtime env vars must disappear from settings and contracts."""
    contracts_by_field = {
        contract.field_name: contract
        for contract in runtime_setting_contracts()
    }

    assert "blocking_io_thread_tokens" not in Settings.model_fields
    assert "blocking_io_thread_tokens" not in contracts_by_field
