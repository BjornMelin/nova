"""Structured logging sanitization tests."""

from __future__ import annotations

from typing import Any

from nova_runtime_support.logging import (
    _DEFAULT_HIDDEN_FIELDS,
    _DEFAULT_REDACTED_SUBSTRINGS,
    _build_redaction_processor,
    _sanitize_log_value,
)


def _sanitize(value: object) -> object:
    return _sanitize_log_value(
        value,
        hidden_fields=_DEFAULT_HIDDEN_FIELDS,
        redacted_substrings=_DEFAULT_REDACTED_SUBSTRINGS,
    )


def test_sanitize_log_value_redacts_presigned_query_signature() -> None:
    """Signature-bearing query strings should be redacted."""
    raw = (
        "https://example.local/object?"
        "X-Amz-Credential=abc&X-Amz-Signature=deadbeef"
    )
    assert _sanitize(raw) == "[REDACTED]"


def test_sanitize_log_value_redacts_nested_sensitive_fields() -> None:
    """Nested URL/token fields should be redacted recursively."""
    payload: dict[str, Any] = {
        "token": "secret-token",
        "nested": {
            "url": "https://example.local/file",
            "ok": True,
        },
    }
    sanitized = _sanitize(payload)
    assert isinstance(sanitized, dict)
    assert sanitized["token"] == "[REDACTED]"
    nested = sanitized["nested"]
    assert isinstance(nested, dict)
    assert nested["url"] == "[REDACTED]"
    assert nested["ok"] is True


def test_redact_sensitive_fields_processor_hides_known_keys() -> None:
    """Structlog processor should redact sensitive top-level keys."""
    event_dict: dict[str, Any] = {
        "message": "request_completed",
        "authorization": "Bearer token-123",
        "presigned_url": "https://example.local/file",
    }
    redact = _build_redaction_processor(
        hidden_fields=_DEFAULT_HIDDEN_FIELDS,
        redacted_substrings=_DEFAULT_REDACTED_SUBSTRINGS,
    )
    redacted = redact(None, "info", event_dict)
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["presigned_url"] == "[REDACTED]"
