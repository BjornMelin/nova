"""Public transfer contract surface for in-process adapter consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from nova_file_api.config import Settings
from nova_file_api.errors import FileTransferError
from nova_file_api.models import (
    AbortUploadRequest,
    AbortUploadResponse,
    CompletedPart,
    CompleteUploadRequest,
    CompleteUploadResponse,
    ErrorEnvelope,
    InitiateUploadRequest,
    InitiateUploadResponse,
    PresignDownloadRequest,
    PresignDownloadResponse,
    Principal,
    SignPartsRequest,
    SignPartsResponse,
    UploadedPart,
    UploadIntrospectionRequest,
    UploadIntrospectionResponse,
    UploadStrategy,
)
from nova_file_api.transfer import TransferService

TRANSFER_ROUTE_PREFIX = "/v1/transfers"
UPLOADS_INITIATE_ROUTE = "/uploads/initiate"
SIGN_PARTS_ROUTE = "/uploads/sign-parts"
INTROSPECT_UPLOAD_ROUTE = "/uploads/introspect"
COMPLETE_UPLOAD_ROUTE = "/uploads/complete"
ABORT_UPLOAD_ROUTE = "/uploads/abort"
PRESIGN_DOWNLOAD_ROUTE = "/downloads/presign"


@dataclass(slots=True, frozen=True)
class TransferFacadeConfig:
    """Typed transfer configuration accepted by adapter-facing factories."""

    file_transfer_enabled: bool
    file_transfer_bucket: str
    file_transfer_upload_prefix: str
    file_transfer_export_prefix: str
    file_transfer_tmp_prefix: str
    file_transfer_presign_upload_ttl_seconds: int
    file_transfer_presign_download_ttl_seconds: int
    file_transfer_multipart_threshold_bytes: int
    file_transfer_part_size_bytes: int
    file_transfer_max_concurrency: int
    file_transfer_use_accelerate_endpoint: bool
    max_upload_bytes: int


def _settings_from_facade_config(config: TransferFacadeConfig) -> Settings:
    """Materialize canonical runtime settings from public transfer config."""

    class _FacadeSettings(Settings):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            del cls
            del (
                settings_cls,
                env_settings,
                dotenv_settings,
                file_secret_settings,
            )
            return (init_settings,)

    default_values = {
        (
            field.alias
            if isinstance(field.alias, str) and field.alias
            else field_name
        ): field.get_default(call_default_factory=True)
        for field_name, field in Settings.model_fields.items()
    }
    default_values.update(
        {
            "FILE_TRANSFER_ENABLED": config.file_transfer_enabled,
            "FILE_TRANSFER_BUCKET": config.file_transfer_bucket,
            "FILE_TRANSFER_UPLOAD_PREFIX": config.file_transfer_upload_prefix,
            "FILE_TRANSFER_EXPORT_PREFIX": config.file_transfer_export_prefix,
            "FILE_TRANSFER_TMP_PREFIX": config.file_transfer_tmp_prefix,
            "FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS": (
                config.file_transfer_presign_upload_ttl_seconds
            ),
            "FILE_TRANSFER_PRESIGN_DOWNLOAD_TTL_SECONDS": (
                config.file_transfer_presign_download_ttl_seconds
            ),
            "FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES": (
                config.file_transfer_multipart_threshold_bytes
            ),
            "FILE_TRANSFER_PART_SIZE_BYTES": (
                config.file_transfer_part_size_bytes
            ),
            "FILE_TRANSFER_MAX_CONCURRENCY": (
                config.file_transfer_max_concurrency
            ),
            "FILE_TRANSFER_USE_ACCELERATE_ENDPOINT": (
                config.file_transfer_use_accelerate_endpoint
            ),
            "FILE_TRANSFER_MAX_UPLOAD_BYTES": config.max_upload_bytes,
        }
    )
    return _FacadeSettings(**default_values)


def build_transfer_service(
    *,
    config: TransferFacadeConfig,
    s3_client: Any,
) -> TransferService:
    """Build the canonical transfer service for bridge consumers.

    Args:
        config: Transfer settings used to materialize runtime configuration.
        s3_client: S3 client dependency passed through to TransferService.

    Returns:
        TransferService: Canonical transfer service instance for adapters.

    Raises:
        ValidationError: If settings derived from config are invalid.
    """
    return TransferService(
        settings=_settings_from_facade_config(config),
        s3_client=s3_client,
    )


__all__ = [
    "ABORT_UPLOAD_ROUTE",
    "COMPLETE_UPLOAD_ROUTE",
    "INTROSPECT_UPLOAD_ROUTE",
    "PRESIGN_DOWNLOAD_ROUTE",
    "SIGN_PARTS_ROUTE",
    "TRANSFER_ROUTE_PREFIX",
    "UPLOADS_INITIATE_ROUTE",
    "AbortUploadRequest",
    "AbortUploadResponse",
    "CompleteUploadRequest",
    "CompleteUploadResponse",
    "CompletedPart",
    "ErrorEnvelope",
    "FileTransferError",
    "InitiateUploadRequest",
    "InitiateUploadResponse",
    "PresignDownloadRequest",
    "PresignDownloadResponse",
    "Principal",
    "SignPartsRequest",
    "SignPartsResponse",
    "TransferFacadeConfig",
    "TransferService",
    "UploadIntrospectionRequest",
    "UploadIntrospectionResponse",
    "UploadStrategy",
    "UploadedPart",
    "build_transfer_service",
]
