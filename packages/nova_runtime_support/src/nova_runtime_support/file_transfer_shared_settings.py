"""Shared env-backed transfer fields for API and workflow Lambda settings."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints

from nova_runtime_support.transfer_limits import (
    ENV_EXPORT_COPY_PART_SIZE_BYTES_MAX,
    ENV_EXPORT_COPY_PART_SIZE_BYTES_MIN,
    ENV_LARGE_EXPORT_WORKER_THRESHOLD_MIN_BYTES,
    ENV_PART_SIZE_BYTES_MAX,
    ENV_PART_SIZE_BYTES_MIN,
    MAX_CONCURRENCY_HINT_MAX,
)


def _none_if_blank(value: object) -> object:
    """Treat blank strings as unset for optional env-backed string fields."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


ConfiguredOptionalEnvString = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    | None,
    BeforeValidator(_none_if_blank),
]


class FileTransferSharedEnvFields(BaseModel):
    """Shared transfer env fields for API and workflow Lambdas.

    Duplicated between ``Settings`` and ``WorkflowSettings`` with identical
    validation — single definition to avoid drift.
    """

    file_transfer_bucket: ConfiguredOptionalEnvString = Field(
        default=None,
        validation_alias="FILE_TRANSFER_BUCKET",
    )

    file_transfer_upload_prefix: str = Field(
        default="uploads/",
        validation_alias="FILE_TRANSFER_UPLOAD_PREFIX",
    )
    file_transfer_export_prefix: str = Field(
        default="exports/",
        validation_alias="FILE_TRANSFER_EXPORT_PREFIX",
    )
    file_transfer_tmp_prefix: str = Field(
        default="tmp/",
        validation_alias="FILE_TRANSFER_TMP_PREFIX",
    )
    file_transfer_part_size_bytes: int = Field(
        default=128 * 1024 * 1024,
        validation_alias="FILE_TRANSFER_PART_SIZE_BYTES",
        ge=ENV_PART_SIZE_BYTES_MIN,
        le=ENV_PART_SIZE_BYTES_MAX,
    )
    file_transfer_export_copy_part_size_bytes: int = Field(
        default=2 * 1024 * 1024 * 1024,
        validation_alias="FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES",
        ge=ENV_EXPORT_COPY_PART_SIZE_BYTES_MIN,
        le=ENV_EXPORT_COPY_PART_SIZE_BYTES_MAX,
    )
    file_transfer_export_copy_max_concurrency: int = Field(
        default=8,
        validation_alias="FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY",
        ge=1,
        le=MAX_CONCURRENCY_HINT_MAX,
    )
    file_transfer_max_concurrency: int = Field(
        default=4,
        validation_alias="FILE_TRANSFER_MAX_CONCURRENCY",
        ge=1,
        le=MAX_CONCURRENCY_HINT_MAX,
    )
    file_transfer_large_export_worker_threshold_bytes: int = Field(
        default=50 * 1024 * 1024 * 1024,
        validation_alias="FILE_TRANSFER_LARGE_EXPORT_WORKER_THRESHOLD_BYTES",
        ge=ENV_LARGE_EXPORT_WORKER_THRESHOLD_MIN_BYTES,
    )
    file_transfer_use_accelerate_endpoint: bool = Field(
        default=False,
        validation_alias="FILE_TRANSFER_USE_ACCELERATE_ENDPOINT",
    )
    file_transfer_upload_sessions_table: ConfiguredOptionalEnvString = Field(
        default=None,
        validation_alias="FILE_TRANSFER_UPLOAD_SESSIONS_TABLE",
    )
    file_transfer_usage_table: ConfiguredOptionalEnvString = Field(
        default=None,
        validation_alias="FILE_TRANSFER_USAGE_TABLE",
    )


__all__ = [
    "ConfiguredOptionalEnvString",
    "FileTransferSharedEnvFields",
]
