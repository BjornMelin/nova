"""Shared helpers for export multipart copy planning and upload metadata."""

from __future__ import annotations

import math
import re
import unicodedata
from pathlib import Path
from typing import Any

_MAX_MULTIPART_PARTS = 10_000
_MIN_MULTIPART_PART_SIZE_BYTES = 5 * 1024 * 1024
_MAX_MULTIPART_PART_SIZE_BYTES = 5 * 1024 * 1024 * 1024


def _sanitize_filename(filename: str) -> str:
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


def _multipart_copy_part_size_bytes(
    *,
    source_size_bytes: int,
    preferred_part_size_bytes: int,
) -> int:
    return min(
        _MAX_MULTIPART_PART_SIZE_BYTES,
        max(
            preferred_part_size_bytes,
            _MIN_MULTIPART_PART_SIZE_BYTES,
            math.ceil(source_size_bytes / _MAX_MULTIPART_PARTS),
        ),
    )


def _multipart_copy_create_upload_kwargs(
    *,
    bucket: str,
    key: str,
    source_object: dict[str, Any],
) -> dict[str, Any]:
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
