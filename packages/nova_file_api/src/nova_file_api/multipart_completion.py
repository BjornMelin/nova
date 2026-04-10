"""Multipart upload completion validation helpers."""

from __future__ import annotations

from typing import Any

from nova_file_api.errors import invalid_request
from nova_file_api.models import CompletedPart
from nova_file_api.upload_sessions import UploadSessionRecord


def build_multipart_completion_payload(
    *,
    requested_parts: list[CompletedPart],
    uploaded_parts: list[tuple[int, str, int]],
    session: UploadSessionRecord | None,
) -> tuple[list[dict[str, Any]], int]:
    """Build the S3 ``CompleteMultipartUpload`` Parts list and total size.

    Args:
        requested_parts: Caller-declared parts (number, etag, optional
            checksum).
        uploaded_parts: Authoritative parts from S3 ``ListParts``, as tuples
            of part number, ETag string, and part size in bytes.
        session: Upload session when checksum policy applies; otherwise
            ``None``.

    Returns:
        A tuple of (parts payload for ``complete_multipart_upload``, sum of part
        sizes in bytes) matching the completed object size.

    Raises:
        invalid_request: Duplicate part numbers, a requested part missing
            from uploads, ETag mismatch vs listed parts, or required checksum
            missing.
    """
    uploaded_parts_by_number = {
        part_number: (etag, size_bytes)
        for part_number, etag, size_bytes in uploaded_parts
    }

    seen_part_numbers: set[int] = set()
    duplicate_part_numbers: set[int] = set()
    for part in requested_parts:
        if part.part_number in seen_part_numbers:
            duplicate_part_numbers.add(part.part_number)
        seen_part_numbers.add(part.part_number)
    if duplicate_part_numbers:
        raise invalid_request(
            "multipart upload part numbers must be unique",
            details={"part_numbers": sorted(duplicate_part_numbers)},
        )

    parts: list[dict[str, Any]] = []
    expected_size_bytes = 0
    for part in sorted(requested_parts, key=lambda item: item.part_number):
        uploaded = uploaded_parts_by_number.get(part.part_number)
        if uploaded is None:
            raise invalid_request(
                "multipart upload part is missing",
                details={"part_number": part.part_number},
            )
        uploaded_etag, size_bytes = uploaded
        if _normalize_etag(uploaded_etag) != _normalize_etag(part.etag):
            raise invalid_request(
                "multipart upload part etag mismatch",
                details={"part_number": part.part_number},
            )
        part_payload: dict[str, Any] = {
            "ETag": uploaded_etag,
            "PartNumber": part.part_number,
        }
        if session is not None and session.checksum_mode == "required":
            if session.checksum_algorithm == "SHA256":
                if part.checksum_sha256 is None:
                    raise invalid_request(
                        (
                            "multipart checksum is required for this "
                            "upload session"
                        ),
                        details={"part_number": part.part_number},
                    )
                part_payload["ChecksumSHA256"] = part.checksum_sha256
        elif part.checksum_sha256 is not None:
            part_payload["ChecksumSHA256"] = part.checksum_sha256
        parts.append(part_payload)
        expected_size_bytes += size_bytes
    return parts, expected_size_bytes


def _normalize_etag(value: str) -> str:
    """Normalize an ETag string for equality comparisons.

    Strips leading/trailing whitespace and surrounding ASCII double quotes.
    S3 often returns quoted ETags (``"abc"``); caller and listed-part values may
    differ in quoting, so compare using normalized forms.
    """
    return value.strip().strip('"')
