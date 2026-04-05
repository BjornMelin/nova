"""Shared helpers for export multipart copy planning and upload metadata."""

from __future__ import annotations

import math
import re
import unicodedata
from pathlib import Path
from typing import Any
from uuid import uuid4

from nova_file_api.s3_coercion import normalize_prefix
from nova_runtime_support.transfer_limits import (
    COPY_OBJECT_MAX_BYTES,
    S3_MULTIPART_MAX_PART_SIZE_BYTES,
    S3_MULTIPART_MAX_PARTS,
    S3_MULTIPART_MIN_PART_SIZE_BYTES,
)


def sanitize_filename(filename: str) -> str:
    """Return one safe filename segment for S3 keys and Content-Disposition.

    Args:
        filename: Original filename or path segment from the caller.

    Returns:
        A sanitized filename segment (no path separators or control characters,
        whitespace collapsed, length capped at 255). Falls back to ``file`` when
        the result would otherwise be empty.
    """
    base_name = unicodedata.normalize("NFC", Path(filename).name)
    allowed_punct = frozenset({".", "-", "_", " "})
    out: list[str] = []
    for ch in base_name:
        if ch in "/\\":
            continue
        if unicodedata.category(ch) == "Cc":
            continue
        if ch in allowed_punct:
            out.append(ch)
            continue
        cat = unicodedata.category(ch)
        if ch.isalnum() or cat.startswith(("L", "M", "N")):
            out.append(ch)
            continue
    merged = re.sub(r"\s+", " ", "".join(out)).strip()
    if len(merged) > 255:
        merged = merged[:255]
    return merged if merged else "file"


def multipart_copy_part_size_bytes(
    *,
    source_size_bytes: int,
    preferred_part_size_bytes: int,
) -> int:
    """Compute MPU part size for server-side multipart copy."""
    return min(
        S3_MULTIPART_MAX_PART_SIZE_BYTES,
        max(
            preferred_part_size_bytes,
            S3_MULTIPART_MIN_PART_SIZE_BYTES,
            math.ceil(source_size_bytes / S3_MULTIPART_MAX_PARTS),
        ),
    )


def multipart_copy_create_upload_kwargs(
    *,
    bucket: str,
    key: str,
    source_object: dict[str, Any],
) -> dict[str, Any]:
    """Build kwargs for CreateMultipartUpload from a source object."""
    kwargs: dict[str, Any] = {"Bucket": bucket, "Key": key}
    for field in (
        "CacheControl",
        "ContentDisposition",
        "ContentEncoding",
        "ContentLanguage",
        "ContentType",
        "Expires",
        "Metadata",
    ):
        value = source_object.get(field)
        if value is not None:
            kwargs[field] = value
    checksum_algorithm = _source_checksum_algorithm(source_object)
    if checksum_algorithm is not None:
        kwargs["ChecksumAlgorithm"] = checksum_algorithm
    return kwargs


def build_export_object_key(
    *,
    export_prefix: str,
    scope_id: str,
    export_id: str,
    filename: str,
) -> str:
    """Build a stable export object key for a pre-sanitized filename.

    Args:
        export_prefix: S3 key prefix; normalized to end with a single ``/``.
        scope_id: Tenant or scope identifier.
        export_id: Export identifier (filtered to alphanumeric, hyphen,
            underscore).
        filename: Pre-sanitized filename (use :func:`sanitize_filename` first);
            must be non-empty and must not contain path separators.

    Returns:
        S3 object key ``{prefix}{scope_id}/{export_id}/{filename}``.

    Raises:
        ValueError: If ``filename`` is empty or contains path separators.
    """
    normalized_prefix = normalize_prefix(export_prefix)
    name = filename.strip()
    if not name:
        raise ValueError("filename must be non-empty")
    if "/" in name or "\\" in name:
        raise ValueError("filename must not contain path separators")
    stable_export_id = "".join(
        character
        for character in export_id.strip()
        if character.isalnum() or character in {"-", "_"}
    )
    if not stable_export_id:
        stable_export_id = uuid4().hex
    return f"{normalized_prefix}{scope_id}/{stable_export_id}/{name}"


def _source_checksum_algorithm(
    source_object: dict[str, Any],
) -> str | None:
    for field in ("ChecksumAlgorithm", "x-amz-checksum-algorithm"):
        value = source_object.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    metadata = source_object.get("Metadata")
    if isinstance(metadata, dict):
        for field in ("ChecksumAlgorithm", "x-amz-checksum-algorithm"):
            value = metadata.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


__all__ = [
    "COPY_OBJECT_MAX_BYTES",
    "build_export_object_key",
    "multipart_copy_create_upload_kwargs",
    "multipart_copy_part_size_bytes",
    "sanitize_filename",
]
