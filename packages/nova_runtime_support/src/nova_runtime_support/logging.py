"""Shared structlog configuration and payload redaction helpers."""

from __future__ import annotations

import logging
from collections.abc import Iterable, MutableMapping
from typing import Any

import structlog

_DEFAULT_HIDDEN_FIELDS = frozenset(
    {
        "access_token",
        "authorization",
        "presigned_url",
        "signature",
        "token",
        "url",
    }
)
_DEFAULT_REDACTED_SUBSTRINGS = (
    "X-Amz-Credential=",
    "X-Amz-Signature=",
)
_LOGGING_CONFIGURED = False


def configure_structlog(
    *,
    hidden_fields: Iterable[str] = (),
    redacted_substrings: Iterable[str] = (),
) -> None:
    """Configure structlog once with Nova-safe redaction defaults."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    hidden = _DEFAULT_HIDDEN_FIELDS | {
        field.strip().lower() for field in hidden_fields if field.strip()
    }
    substrings = _DEFAULT_REDACTED_SUBSTRINGS + tuple(redacted_substrings)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _build_redaction_processor(
                hidden_fields=hidden,
                redacted_substrings=substrings,
            ),
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _LOGGING_CONFIGURED = True


def _build_redaction_processor(
    *,
    hidden_fields: frozenset[str],
    redacted_substrings: tuple[str, ...],
) -> Any:
    def redact(
        _logger: Any,
        _method_name: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        return {
            key: _sanitize_log_value(
                value,
                hidden_fields=hidden_fields,
                redacted_substrings=redacted_substrings,
                key_name=key,
            )
            for key, value in event_dict.items()
        }

    return redact


def _sanitize_log_value(
    value: object,
    *,
    hidden_fields: frozenset[str],
    redacted_substrings: tuple[str, ...],
    key_name: str | None = None,
) -> object:
    normalized_key = key_name.lower() if isinstance(key_name, str) else None
    if normalized_key in hidden_fields:
        return "[REDACTED]"
    if isinstance(value, str):
        if any(marker in value for marker in redacted_substrings):
            return "[REDACTED]"
        return value
    if isinstance(value, dict):
        return {
            key: _sanitize_log_value(
                item,
                hidden_fields=hidden_fields,
                redacted_substrings=redacted_substrings,
                key_name=key,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _sanitize_log_value(
                item,
                hidden_fields=hidden_fields,
                redacted_substrings=redacted_substrings,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            _sanitize_log_value(
                item,
                hidden_fields=hidden_fields,
                redacted_substrings=redacted_substrings,
            )
            for item in value
        )
    return value
