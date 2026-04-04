"""Workflow task runtime settings."""

from __future__ import annotations

from pydantic import Field, model_validator
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
    file_transfer_export_copy_part_size_bytes: int = Field(
        default=2 * 1024 * 1024 * 1024,
        validation_alias="FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES",
        ge=1 * 1024 * 1024 * 1024,
        le=5 * 1024 * 1024 * 1024,
    )
    file_transfer_export_copy_max_concurrency: int = Field(
        default=8,
        validation_alias="FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY",
        ge=1,
        le=32,
    )
    file_transfer_large_export_worker_threshold_bytes: int = Field(
        default=50 * 1024 * 1024 * 1024,
        validation_alias="FILE_TRANSFER_LARGE_EXPORT_WORKER_THRESHOLD_BYTES",
        ge=5 * 1024 * 1024 * 1024,
    )
    file_transfer_export_copy_worker_attempts: int = Field(
        default=5,
        validation_alias="FILE_TRANSFER_EXPORT_COPY_WORKER_ATTEMPTS",
        ge=1,
        le=20,
    )
    file_transfer_export_copy_worker_lease_seconds: int = Field(
        default=30 * 60,
        validation_alias="FILE_TRANSFER_EXPORT_COPY_WORKER_LEASE_SECONDS",
        ge=60,
        le=24 * 60 * 60,
    )
    file_transfer_export_copy_parts_table: str | None = Field(
        default=None,
        validation_alias="FILE_TRANSFER_EXPORT_COPY_PARTS_TABLE",
    )
    file_transfer_export_copy_queue_url: str | None = Field(
        default=None,
        validation_alias="FILE_TRANSFER_EXPORT_COPY_QUEUE_URL",
    )
    file_transfer_max_concurrency: int = Field(
        default=4,
        validation_alias="FILE_TRANSFER_MAX_CONCURRENCY",
        ge=1,
        le=32,
    )
    file_transfer_upload_sessions_table: str | None = Field(
        default=None,
        validation_alias="FILE_TRANSFER_UPLOAD_SESSIONS_TABLE",
    )
    file_transfer_stale_multipart_cleanup_age_seconds: int = Field(
        default=24 * 60 * 60,
        validation_alias="FILE_TRANSFER_STALE_MULTIPART_CLEANUP_AGE_SECONDS",
        ge=60,
    )
    file_transfer_reconciliation_scan_limit: int = Field(
        default=200,
        validation_alias="FILE_TRANSFER_RECONCILIATION_SCAN_LIMIT",
        ge=1,
        le=1000,
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
    file_transfer_usage_table: str | None = Field(
        default=None,
        validation_alias="FILE_TRANSFER_USAGE_TABLE",
    )
    metrics_namespace: str = Field(
        default="NovaFileApi",
        validation_alias="METRICS_NAMESPACE",
    )

    @model_validator(mode="after")
    def validate_exports_dynamodb_table(self) -> WorkflowSettings:
        """Require durable export state storage when exports are enabled."""
        if self.exports_enabled and not (
            self.exports_dynamodb_table and self.exports_dynamodb_table.strip()
        ):
            raise ValueError(
                "EXPORTS_DYNAMODB_TABLE must be configured when "
                "EXPORTS_ENABLED=true"
            )
        return self

    @model_validator(mode="after")
    def validate_export_copy_worker_backends_pair(self) -> WorkflowSettings:
        """Require copy-parts table and worker queue together."""
        table = (self.file_transfer_export_copy_parts_table or "").strip()
        queue = (self.file_transfer_export_copy_queue_url or "").strip()
        if bool(table) != bool(queue):
            raise ValueError(
                "FILE_TRANSFER_EXPORT_COPY_PARTS_TABLE and "
                "FILE_TRANSFER_EXPORT_COPY_QUEUE_URL must both be configured "
                "together (or both omitted)"
            )
        return self


def export_transfer_config_from_settings(
    settings: WorkflowSettings,
) -> ExportTransferConfig:
    """Project workflow settings onto the export-copy transfer seam.

    Args:
        settings: Resolved workflow runtime settings.

    Returns:
        Export transfer configuration derived from workflow settings.

    Raises:
        ValueError: If the configured transfer bucket is blank after trimming.
    """
    bucket = settings.file_transfer_bucket.strip()
    if not bucket:
        raise ValueError("FILE_TRANSFER_BUCKET must be configured")
    return ExportTransferConfig(
        bucket=bucket,
        upload_prefix=settings.file_transfer_upload_prefix,
        export_prefix=settings.file_transfer_export_prefix,
        tmp_prefix=settings.file_transfer_tmp_prefix,
        part_size_bytes=settings.file_transfer_export_copy_part_size_bytes,
        max_concurrency=settings.file_transfer_export_copy_max_concurrency,
        copy_part_size_bytes=settings.file_transfer_export_copy_part_size_bytes,
        copy_max_concurrency=settings.file_transfer_export_copy_max_concurrency,
        large_copy_worker_threshold_bytes=(
            settings.file_transfer_large_export_worker_threshold_bytes
        ),
    )
