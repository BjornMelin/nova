"""Structured logging sanitization tests."""

from __future__ import annotations

from typing import Any

from nova_file_api.log_sanitization import (
    redact_sensitive_fields,
    sanitize_log_value,
    sanitize_validation_errors,
)


def test_sanitize_log_value_redacts_presigned_query_signature() -> None:
    """Signature-bearing query strings should be redacted."""
    raw = (
        "https://example.local/object?"
        "X-Amz-Credential=abc&X-Amz-Signature=deadbeef"
    )
    assert sanitize_log_value(raw) == "[REDACTED]"


def test_sanitize_log_value_redacts_presigned_query_signature_in_bytes() -> (
    None
):
    """Decoded bytes must still run presigned-signature redaction."""
    raw = (
        b"https://example.local/object?"
        b"X-Amz-Credential=abc&X-Amz-Signature=deadbeef"
    )
    assert sanitize_log_value(raw) == "[REDACTED]"


def test_sanitize_log_value_redacts_nested_sensitive_fields() -> None:
    """Nested URL/token fields should be redacted recursively."""
    payload: dict[str, Any] = {
        "token": "secret-token",
        "nested": {
            "url": "https://example.local/file",
            "ok": True,
        },
    }
    sanitized = sanitize_log_value(payload)
    assert isinstance(sanitized, dict)
    assert sanitized["token"] == "[REDACTED]"
    nested = sanitized["nested"]
    assert isinstance(nested, dict)
    assert nested["url"] == "[REDACTED]"
    assert nested["ok"] is True


def test_sanitize_validation_errors_redacts_authorization_header() -> None:
    """Authorization header validation errors should redact token input."""
    raw_error = {
        "loc": ("header", "authorization"),
        "input": "Bearer very-secret-token",
        "msg": "field required",
    }
    sanitized_errors = sanitize_validation_errors(errors=[raw_error])
    sanitized_error = sanitized_errors[0]
    assert isinstance(sanitized_error, dict)
    assert sanitized_error["input"] == "[REDACTED]"

    logged_payload = redact_sensitive_fields(
        None,
        "info",
        {"validation_errors": sanitized_errors},
    )
    assert "very-secret-token" not in str(logged_payload)
    assert "Bearer" not in str(logged_payload)


def test_redact_sensitive_fields_processor_hides_known_keys() -> None:
    """Structlog processor should redact sensitive top-level keys."""
    event_dict: dict[str, Any] = {
        "message": "request_completed",
        "authorization": "Bearer token-123",
        "presigned_url": "https://example.local/file",
    }
    redacted = redact_sensitive_fields(None, "info", event_dict)
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["presigned_url"] == "[REDACTED]"
