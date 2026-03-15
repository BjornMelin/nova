"""Public transfer contract surface for in-process adapter consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nova_file_api.config import Settings
from nova_file_api.errors import FileTransferError
from nova_file_api.models import (
    AbortUploadRequest,
    AbortUploadResponse,
    CompletedPart,
    CompleteUploadRequest,
    CompleteUploadResponse,
    ErrorBody,
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
    default_values = {
        field_name: field.get_default(call_default_factory=True)
        for field_name, field in Settings.model_fields.items()
    }
    default_values.update(
        {
            "file_transfer_enabled": config.file_transfer_enabled,
            "file_transfer_bucket": config.file_transfer_bucket,
            "file_transfer_upload_prefix": config.file_transfer_upload_prefix,
            "file_transfer_export_prefix": config.file_transfer_export_prefix,
            "file_transfer_tmp_prefix": config.file_transfer_tmp_prefix,
            "file_transfer_presign_upload_ttl_seconds": (
                config.file_transfer_presign_upload_ttl_seconds
            ),
            "file_transfer_presign_download_ttl_seconds": (
                config.file_transfer_presign_download_ttl_seconds
            ),
            "file_transfer_multipart_threshold_bytes": (
                config.file_transfer_multipart_threshold_bytes
            ),
            "file_transfer_part_size_bytes": (
                config.file_transfer_part_size_bytes
            ),
            "file_transfer_max_concurrency": (
                config.file_transfer_max_concurrency
            ),
            "file_transfer_use_accelerate_endpoint": (
                config.file_transfer_use_accelerate_endpoint
            ),
            "max_upload_bytes": config.max_upload_bytes,
        }
    )
    settings = Settings.model_construct(**default_values)
    max_supported_upload_bytes = settings.file_transfer_part_size_bytes * 10_000
    if settings.max_upload_bytes > max_supported_upload_bytes:
        raise ValueError(
            "FILE_TRANSFER_MAX_UPLOAD_BYTES must be less than or equal to "
            "FILE_TRANSFER_PART_SIZE_BYTES * 10000"
        )
    return settings


def build_transfer_service(
    *,
    config: TransferFacadeConfig,
    s3_client: Any,
) -> TransferService:
    """Build the canonical transfer service for bridge consumers."""
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
    "ErrorBody",
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
