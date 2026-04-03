"""Plain transfer-service configuration shared across runtime and adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nova_file_api.config import Settings


@dataclass(slots=True, frozen=True, kw_only=True)
class TransferConfig:
    """Explicit transfer-scoped runtime configuration."""

    enabled: bool
    bucket: str
    upload_prefix: str
    export_prefix: str
    tmp_prefix: str
    presign_upload_ttl_seconds: int
    presign_download_ttl_seconds: int
    multipart_threshold_bytes: int
    part_size_bytes: int
    export_copy_part_size_bytes: int
    max_concurrency: int
    export_copy_max_concurrency: int
    target_upload_part_count: int
    use_accelerate_endpoint: bool
    max_upload_bytes: int
    policy_id: str
    policy_version: str
    active_multipart_upload_limit: int | None
    daily_ingress_budget_bytes: int | None
    sign_requests_per_upload_limit: int | None
    resumable_window_seconds: int
    checksum_algorithm: str | None
    upload_sessions_table: str | None
    usage_table: str | None
    policy_appconfig_application: str | None
    policy_appconfig_environment: str | None
    policy_appconfig_profile: str | None
    policy_appconfig_poll_interval_seconds: int

    def upload_part_size_bytes(self, *, size_bytes: int) -> int:
        """Resolve the upload part size for one object size."""
        return _bounded_part_size_bytes(
            size_bytes=size_bytes,
            preferred_part_size_bytes=self.part_size_bytes,
            target_part_count=self.target_upload_part_count,
            minimum_part_size_bytes=64 * 1024 * 1024,
            maximum_part_size_bytes=512 * 1024 * 1024,
        )

    def sign_batch_size_hint(self) -> int:
        """Return the recommended batch size for presigning multipart parts."""
        return min(128, max(32, self.max_concurrency * 4))

    def resumable_until(self, *, created_at: datetime) -> datetime:
        """Return the session expiry timestamp for one upload."""
        base = (
            created_at
            if created_at.tzinfo is not None
            else created_at.replace(tzinfo=UTC)
        )
        return base + timedelta(seconds=self.resumable_window_seconds)

    def export_copy_part_size_bytes_for(self, *, size_bytes: int) -> int:
        """Resolve the server-side multipart copy part size for one object."""
        return _bounded_part_size_bytes(
            size_bytes=size_bytes,
            preferred_part_size_bytes=self.export_copy_part_size_bytes,
            target_part_count=max(1, self.export_copy_max_concurrency * 2),
            minimum_part_size_bytes=1 * 1024 * 1024 * 1024,
            maximum_part_size_bytes=5 * 1024 * 1024 * 1024,
        )


def transfer_config_from_settings(settings: Settings) -> TransferConfig:
    """Project the runtime settings object onto transfer-specific config.

    Args:
        settings: Runtime settings that provide the file transfer fields.

    Returns:
        TransferConfig: Plain transfer-scoped configuration for service setup.
    """
    return TransferConfig(
        enabled=settings.file_transfer_enabled,
        bucket=settings.file_transfer_bucket,
        upload_prefix=settings.file_transfer_upload_prefix,
        export_prefix=settings.file_transfer_export_prefix,
        tmp_prefix=settings.file_transfer_tmp_prefix,
        presign_upload_ttl_seconds=(
            settings.file_transfer_presign_upload_ttl_seconds
        ),
        presign_download_ttl_seconds=(
            settings.file_transfer_presign_download_ttl_seconds
        ),
        multipart_threshold_bytes=(
            settings.file_transfer_multipart_threshold_bytes
        ),
        part_size_bytes=settings.file_transfer_part_size_bytes,
        export_copy_part_size_bytes=(
            settings.file_transfer_export_copy_part_size_bytes
        ),
        max_concurrency=settings.file_transfer_max_concurrency,
        export_copy_max_concurrency=(
            settings.file_transfer_export_copy_max_concurrency
        ),
        target_upload_part_count=settings.file_transfer_target_upload_part_count,
        use_accelerate_endpoint=settings.file_transfer_use_accelerate_endpoint,
        max_upload_bytes=settings.max_upload_bytes,
        policy_id=settings.file_transfer_policy_id,
        policy_version=settings.file_transfer_policy_version,
        active_multipart_upload_limit=(
            settings.file_transfer_active_multipart_upload_limit
        ),
        daily_ingress_budget_bytes=(
            settings.file_transfer_daily_ingress_budget_bytes
        ),
        sign_requests_per_upload_limit=(
            settings.file_transfer_sign_requests_per_upload_limit
        ),
        resumable_window_seconds=(
            settings.file_transfer_resumable_window_seconds
        ),
        checksum_algorithm=settings.file_transfer_checksum_algorithm,
        upload_sessions_table=settings.file_transfer_upload_sessions_table,
        usage_table=settings.file_transfer_usage_table,
        policy_appconfig_application=_normalized_optional_identifier(
            settings.file_transfer_policy_appconfig_application
        ),
        policy_appconfig_environment=_normalized_optional_identifier(
            settings.file_transfer_policy_appconfig_environment
        ),
        policy_appconfig_profile=_normalized_optional_identifier(
            settings.file_transfer_policy_appconfig_profile
        ),
        policy_appconfig_poll_interval_seconds=(
            settings.file_transfer_policy_appconfig_poll_interval_seconds
        ),
    )


def _normalized_optional_identifier(value: str | None) -> str | None:
    """Return a stripped identifier or ``None`` when empty."""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _bounded_part_size_bytes(
    *,
    size_bytes: int,
    preferred_part_size_bytes: int,
    target_part_count: int,
    minimum_part_size_bytes: int,
    maximum_part_size_bytes: int,
) -> int:
    """Return a bounded multipart part size."""
    return min(
        maximum_part_size_bytes,
        max(
            minimum_part_size_bytes,
            preferred_part_size_bytes,
            -(-size_bytes // target_part_count),
        ),
    )


__all__ = ["TransferConfig", "transfer_config_from_settings"]
