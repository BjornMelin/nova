"""Configuration contract tests for runtime settings parsing."""

from __future__ import annotations

import pytest
from nova_file_api.config import Settings, _parse_string_tuple


def test_parse_string_tuple_reports_clear_allowed_origins_json_error() -> None:
    expected_message = (
        "ALLOWED_ORIGINS must be a valid JSON array or comma-delimited string"
    )
    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        _parse_string_tuple("[not-json")


def test_resolved_cors_allowed_origins_uses_dev_defaults_without_stack_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STACK_ALLOWED_ORIGINS", "https://stack.example.com")

    settings = Settings.model_validate(
        {
            "environment": "dev",
            "idempotency_dynamodb_table": "test-idempotency",
        }
    )

    assert settings.resolved_cors_allowed_origins == (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8050",
        "http://127.0.0.1:8050",
    )
