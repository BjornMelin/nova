"""Plain transfer-service configuration shared across runtime and adapters."""

from __future__ import annotations

from dataclasses import dataclass
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
    max_concurrency: int
    use_accelerate_endpoint: bool
    max_upload_bytes: int


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
        max_concurrency=settings.file_transfer_max_concurrency,
        use_accelerate_endpoint=settings.file_transfer_use_accelerate_endpoint,
        max_upload_bytes=settings.max_upload_bytes,
    )


__all__ = ["TransferConfig", "transfer_config_from_settings"]
