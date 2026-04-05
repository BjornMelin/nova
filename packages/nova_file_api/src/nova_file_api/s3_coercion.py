"""Shared helpers for normalizing S3 client responses and key prefixes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def normalize_prefix(prefix: str) -> str:
    """Normalize a key prefix for S3-style hierarchical keys.

    Args:
        prefix: Raw prefix string (may include leading/trailing whitespace).

    Returns:
        ``""`` if ``prefix`` is empty after stripping; otherwise the trimmed
        value with a trailing ``/`` appended when missing.
    """
    normalized = prefix.strip()
    if not normalized:
        return ""
    if not normalized.endswith("/"):
        normalized = f"{normalized}/"
    return normalized


def opt_str(value: object) -> str | None:
    """Coerce a wire value to ``str`` when it is already a string.

    Args:
        value: Any object from an S3 client response or similar payload.

    Returns:
        ``value`` if it is a ``str``; otherwise ``None``.
    """
    if isinstance(value, str):
        return value
    return None


def parse_positive_int(
    value: Any,
    *,
    error_message: str,
    err: Callable[[str], Exception],
) -> int:
    """Parse a strictly positive int from common S3 wire shapes.

    Args:
        value: Raw scalar (often ``int`` or numeric string) from S3 XML/JSON.
        error_message: Message passed to ``err`` on failure.
        err: Factory returning the exception to raise on parse failure.

    Returns:
        A positive ``int`` (never zero or negative).

    Raises:
        Exception: ``err(error_message)`` when ``value`` is invalid, including
        booleans, non-positive integers, unparsable strings, or zero.
    """
    if isinstance(value, bool):
        raise err(error_message)
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            parsed = 0
        if parsed > 0:
            return parsed
    raise err(error_message)


def parse_non_negative_int(
    value: Any,
    *,
    error_message: str,
    err: Callable[[str], Exception],
) -> int:
    """Parse a non-negative int from common S3 wire shapes.

    Args:
        value: Raw scalar (often ``int`` or numeric string) from S3 XML/JSON.
        error_message: Message passed to ``err`` on failure.
        err: Factory returning the exception to raise on parse failure.

    Returns:
        A non-negative ``int``.

    Raises:
        Exception: ``err(error_message)`` when ``value`` is invalid, including
        booleans, negative integers, or unparsable strings.
    """
    if isinstance(value, bool):
        raise err(error_message)
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            parsed = -1
        if parsed >= 0:
            return parsed
    raise err(error_message)


def copy_part_etag(
    response: dict[str, Any],
    *,
    err: Callable[[str], Exception],
) -> str:
    """Extract the ETag string from an UploadPartCopy response dict.

    Args:
        response: Boto-style response mapping, expected to include
            ``CopyPartResult`` with an ``ETag`` string.
        err: Factory for exceptions when the payload is malformed.

    Returns:
        The copy-part ETag string (quotes preserved as returned by S3).

    Raises:
        Exception: ``err("multipart export copy part result is missing")`` when
        ``CopyPartResult`` is missing or not a ``dict``.
        Exception: ``err("multipart export copy part etag is missing")`` when
        ``ETag`` is absent or not a string (including wrong types).
    """
    copy_result = response.get("CopyPartResult")
    if not isinstance(copy_result, dict):
        raise err("multipart export copy part result is missing")
    etag = opt_str(copy_result.get("ETag"))
    if etag is None:
        raise err("multipart export copy part etag is missing")
    return etag
