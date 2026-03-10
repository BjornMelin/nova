"""Shared structured-log and validation-error sanitization helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

HIDDEN_FIELDS = {
    "token",
    "authorization",
    "url",
    "presigned_url",
    "signature",
}


def sanitize_log_value(value: Any) -> Any:
    """Redact nested sensitive values before they reach logs."""
    if isinstance(value, dict):
        output: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in HIDDEN_FIELDS:
                output[key] = "[REDACTED]"
            else:
                output[key] = sanitize_log_value(item)
        return output
    if isinstance(value, list):
        return [sanitize_log_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_log_value(item) for item in value)
    if isinstance(value, str) and "x-amz-signature=" in value.lower():
        return "[REDACTED]"
    return value


def redact_sensitive_fields(
    _logger: Any,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Redact top-level and nested sensitive logging fields."""
    output: dict[str, Any] = {}
    for key, value in event_dict.items():
        if key.lower() in HIDDEN_FIELDS:
            output[key] = "[REDACTED]"
        else:
            output[key] = sanitize_log_value(value)
    return output


def sanitize_validation_errors(*, errors: Sequence[Any]) -> list[Any]:
    """Return validation errors with nested sensitive values redacted."""
    sanitized: list[Any] = []
    for error in errors:
        if isinstance(error, dict):
            sanitized.append(sanitize_log_value(error))
        else:
            sanitized.append(error)
    return sanitized
