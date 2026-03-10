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
    """
    Sanitize a value for logging by redacting sensitive fields and signatures.
    
    Recursively walks dictionaries, lists, and tuples to redact sensitive data: dictionary entries whose string key (case-insensitive) is in HIDDEN_FIELDS are replaced with "[REDACTED]"; strings containing "x-amz-signature=" (case-insensitive) are replaced with "[REDACTED]". Other values are returned unchanged.
    
    Parameters:
        value (Any): Input value to sanitize; may be a dict, list, tuple, string, or any other type.
    
    Returns:
        Any: The sanitized value with sensitive fields and signatures replaced by "[REDACTED]".
    """
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
    """
    Redact sensitive top-level keys and sanitize nested values in an event dictionary.
    
    Parameters:
        event_dict: Event dictionary to sanitize. Top-level keys whose lowercase form is in HIDDEN_FIELDS are replaced with "[REDACTED]"; all other values are recursively sanitized.
    
    Returns:
        A new dictionary where sensitive top-level keys are replaced with "[REDACTED]" and nested sensitive values are sanitized.
    """
    output: dict[str, Any] = {}
    for key, value in event_dict.items():
        if key.lower() in HIDDEN_FIELDS:
            output[key] = "[REDACTED]"
        else:
            output[key] = sanitize_log_value(value)
    return output


def sanitize_validation_errors(*, errors: Sequence[Any]) -> list[Any]:
    """
    Produce a list of validation errors with sensitive fields redacted.
    
    Parameters:
        errors (Sequence[Any]): Sequence of validation error items; dictionary items will have nested sensitive fields redacted.
    
    Returns:
        list[Any]: A list where each dictionary error has been sanitized and non-dictionary errors are returned unchanged.
    """
    sanitized: list[Any] = []
    for error in errors:
        if isinstance(error, dict):
            sanitized.append(sanitize_log_value(error))
        else:
            sanitized.append(error)
    return sanitized