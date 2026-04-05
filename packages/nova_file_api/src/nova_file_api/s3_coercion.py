"""Shared helpers for normalizing S3 client responses and key prefixes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def normalize_prefix(prefix: str) -> str:
    """Strip and ensure a trailing slash when non-empty."""
    normalized = prefix.strip()
    if not normalized:
        return ""
    if not normalized.endswith("/"):
        normalized = f"{normalized}/"
    return normalized


def opt_str(value: object) -> str | None:
    """Return value if it is a str, else None."""
    if isinstance(value, str):
        return value
    return None


def parse_positive_int(
    value: Any,
    *,
    error_message: str,
    err: Callable[[str], Exception],
) -> int:
    """Parse a strictly positive int from common S3 wire shapes."""
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
    """Parse a non-negative int from common S3 wire shapes."""
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
    """Extract ETag from an UploadPartCopy response dict."""
    copy_result = response.get("CopyPartResult")
    if not isinstance(copy_result, dict):
        raise err("multipart export copy part result is missing")
    etag = opt_str(copy_result.get("ETag"))
    if etag is None:
        raise err("multipart export copy part etag is missing")
    return etag
