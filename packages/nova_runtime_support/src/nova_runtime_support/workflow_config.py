"""Workflow task runtime settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from nova_runtime_support.export_transfer import ExportTransferConfig


class WorkflowSettings(BaseSettings):
    """Runtime settings loaded by workflow task handlers."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=False,
    )

    file_transfer_bucket: str = Field(
        default="",
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
        ge=5 * 1024 * 1024,
        le=5 * 1024 * 1024 * 1024,
    )
    file_transfer_max_concurrency: int = Field(
        default=4,
        validation_alias="FILE_TRANSFER_MAX_CONCURRENCY",
        ge=1,
        le=32,
    )
    file_transfer_use_accelerate_endpoint: bool = Field(
        default=False,
        validation_alias="FILE_TRANSFER_USE_ACCELERATE_ENDPOINT",
    )
    exports_enabled: bool = Field(
        default=True,
        validation_alias="EXPORTS_ENABLED",
    )
    exports_dynamodb_table: str | None = Field(
        default=None,
        validation_alias="EXPORTS_DYNAMODB_TABLE",
    )


def export_transfer_config_from_settings(
    settings: WorkflowSettings,
) -> ExportTransferConfig:
    """Project workflow settings onto the export-copy transfer seam."""
    return ExportTransferConfig(
        bucket=settings.file_transfer_bucket,
        upload_prefix=settings.file_transfer_upload_prefix,
        export_prefix=settings.file_transfer_export_prefix,
        tmp_prefix=settings.file_transfer_tmp_prefix,
        part_size_bytes=settings.file_transfer_part_size_bytes,
        max_concurrency=settings.file_transfer_max_concurrency,
    )
