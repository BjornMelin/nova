"""Shared transfer policy document contract."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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
        ge=5 * 1024 * 1024,
    )
    target_upload_part_count: int | None = Field(default=None, ge=1, le=10_000)
    upload_part_size_bytes: int | None = Field(
        default=None,
        ge=64 * 1024 * 1024,
        le=512 * 1024 * 1024,
    )
    max_concurrency_hint: int | None = Field(default=None, ge=1, le=32)
    sign_batch_size_hint: int | None = Field(default=None, ge=32, le=128)
    accelerate_enabled: bool | None = None
    checksum_algorithm: str | None = None
    resumable_ttl_seconds: int | None = Field(
        default=None,
        ge=60,
        le=30 * 24 * 60 * 60,
    )
    active_multipart_upload_limit: int | None = Field(default=None, ge=1)
    daily_ingress_budget_bytes: int | None = Field(default=None, ge=1)
    sign_requests_per_upload_limit: int | None = Field(default=None, ge=1)
