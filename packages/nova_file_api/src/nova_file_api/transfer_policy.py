"""Transfer policy resolution for public file-transfer endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from nova_file_api.transfer_config import TransferConfig

_DEFAULT_POLICY_ID = "default"
_DEFAULT_POLICY_VERSION = "2026-04-03"
_TARGET_UPLOAD_PART_COUNT = 2000
_MINIMUM_UPLOAD_PART_SIZE_BYTES = 64 * 1024 * 1024
_MAXIMUM_UPLOAD_PART_SIZE_BYTES = 512 * 1024 * 1024
_MIN_SIGN_BATCH_SIZE = 32
_MAX_SIGN_BATCH_SIZE = 128
_MIN_CONCURRENCY_FOR_SIGN_BATCH = 4


@dataclass(slots=True, frozen=True, kw_only=True)
class TransferPolicy:
    """Resolved transfer policy for one caller and file size."""

    policy_id: str
    policy_version: str
    max_upload_bytes: int
    multipart_threshold_bytes: int
    target_upload_part_count: int
    minimum_part_size_bytes: int
    maximum_part_size_bytes: int
    upload_part_size_bytes: int
    max_concurrency_hint: int
    sign_batch_size_hint: int
    accelerate_enabled: bool
    checksum_algorithm: str | None
    resumable_ttl_seconds: int


def resolve_transfer_policy(
    *,
    config: TransferConfig,
) -> TransferPolicy:
    """Resolve the current transfer policy from static runtime settings."""
    target_upload_part_count = (
        config.target_upload_part_count or _TARGET_UPLOAD_PART_COUNT
    )
    max_concurrency_hint = config.max_concurrency
    sign_batch_size_hint = _clamp(
        max(_MIN_SIGN_BATCH_SIZE, max_concurrency_hint * 4),
        _MIN_SIGN_BATCH_SIZE,
        _MAX_SIGN_BATCH_SIZE,
    )
    return TransferPolicy(
        policy_id=config.policy_id or _DEFAULT_POLICY_ID,
        policy_version=config.policy_version or _DEFAULT_POLICY_VERSION,
        max_upload_bytes=config.max_upload_bytes,
        multipart_threshold_bytes=config.multipart_threshold_bytes,
        target_upload_part_count=target_upload_part_count,
        minimum_part_size_bytes=_MINIMUM_UPLOAD_PART_SIZE_BYTES,
        maximum_part_size_bytes=_MAXIMUM_UPLOAD_PART_SIZE_BYTES,
        upload_part_size_bytes=config.part_size_bytes,
        max_concurrency_hint=max_concurrency_hint,
        sign_batch_size_hint=sign_batch_size_hint,
        accelerate_enabled=config.use_accelerate_endpoint,
        checksum_algorithm=config.checksum_algorithm,
        resumable_ttl_seconds=config.resumable_window_seconds,
    )


def upload_part_size_bytes(
    *,
    file_size_bytes: int,
    policy: TransferPolicy,
) -> int:
    """Return the upload part size for one file under the resolved policy."""
    candidate_size = ceil(file_size_bytes / policy.target_upload_part_count)
    return _clamp(
        max(policy.upload_part_size_bytes, candidate_size),
        policy.minimum_part_size_bytes,
        policy.maximum_part_size_bytes,
    )


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))
