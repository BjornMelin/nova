"""Shared transfer policy document contract."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from nova_runtime_support.transfer_limits import (
    CLIENT_UPLOAD_MAX_PART_SIZE_BYTES,
    CLIENT_UPLOAD_MIN_PART_SIZE_BYTES,
    ENV_LARGE_EXPORT_WORKER_THRESHOLD_MIN_BYTES,
    MAX_CONCURRENCY_HINT_MAX,
    MAX_CONCURRENCY_HINT_MIN,
    MULTIPART_THRESHOLD_MIN_BYTES,
    RESUMABLE_TTL_MAX_SECONDS,
    RESUMABLE_TTL_MIN_SECONDS,
    SIGN_BATCH_SIZE_HINT_MAX,
    SIGN_BATCH_SIZE_HINT_MIN,
    TARGET_UPLOAD_PART_COUNT_MAX,
    TARGET_UPLOAD_PART_COUNT_MIN,
)


class TransferPolicyDocument(BaseModel):
    """Runtime transfer policy payload shared by runtime and infra code."""

    model_config = ConfigDict(extra="forbid")

    policy_id: str | None = Field(default=None, min_length=1, max_length=128)
    policy_version: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
    )
    max_upload_bytes: int | None = Field(default=None, ge=1)
    multipart_threshold_bytes: int | None = Field(
        default=None,
        ge=MULTIPART_THRESHOLD_MIN_BYTES,
    )
    target_upload_part_count: int | None = Field(
        default=None,
        ge=TARGET_UPLOAD_PART_COUNT_MIN,
        le=TARGET_UPLOAD_PART_COUNT_MAX,
    )
    upload_part_size_bytes: int | None = Field(
        default=None,
        ge=CLIENT_UPLOAD_MIN_PART_SIZE_BYTES,
        le=CLIENT_UPLOAD_MAX_PART_SIZE_BYTES,
    )
    max_concurrency_hint: int | None = Field(
        default=None,
        ge=MAX_CONCURRENCY_HINT_MIN,
        le=MAX_CONCURRENCY_HINT_MAX,
    )
    sign_batch_size_hint: int | None = Field(
        default=None,
        ge=SIGN_BATCH_SIZE_HINT_MIN,
        le=SIGN_BATCH_SIZE_HINT_MAX,
    )
    accelerate_enabled: bool | None = None
    checksum_algorithm: str | None = None
    resumable_ttl_seconds: int | None = Field(
        default=None,
        ge=RESUMABLE_TTL_MIN_SECONDS,
        le=RESUMABLE_TTL_MAX_SECONDS,
    )
    active_multipart_upload_limit: int | None = Field(default=None, ge=1)
    daily_ingress_budget_bytes: int | None = Field(default=None, ge=1)
    sign_requests_per_upload_limit: int | None = Field(default=None, ge=1)
    checksum_mode: str | None = Field(
        default=None,
        pattern="^(none|optional|required)$",
    )
    large_export_worker_threshold_bytes: int | None = Field(
        default=None,
        ge=ENV_LARGE_EXPORT_WORKER_THRESHOLD_MIN_BYTES,
    )
    profiles: dict[str, TransferPolicyDocument] | None = None


TransferPolicyDocument.model_rebuild()
