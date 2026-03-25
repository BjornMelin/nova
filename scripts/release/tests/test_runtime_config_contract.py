from __future__ import annotations

from nova_file_api.config import Settings

from scripts.release.runtime_config_contract import runtime_setting_contracts


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
