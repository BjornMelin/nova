"""Public transfer contract surface for in-process adapter consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

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


class AsyncTransferService(Protocol):
    """Async transfer operations exposed to adapter consumers."""

    async def initiate_upload(
        self,
        request: InitiateUploadRequest,
        principal: Principal,
    ) -> InitiateUploadResponse:
        """Start an upload for the authenticated principal."""
        ...

    async def sign_parts(
        self,
        request: SignPartsRequest,
        principal: Principal,
    ) -> SignPartsResponse:
        """Presign multipart part uploads for a caller-owned key."""
        ...

    async def introspect_upload(
        self,
        request: UploadIntrospectionRequest,
        principal: Principal,
    ) -> UploadIntrospectionResponse:
        """Inspect multipart upload state for a caller-owned key."""
        ...

    async def complete_upload(
        self,
        request: CompleteUploadRequest,
        principal: Principal,
    ) -> CompleteUploadResponse:
        """Complete a caller-owned multipart upload."""
        ...

    async def abort_upload(
        self,
        request: AbortUploadRequest,
        principal: Principal,
    ) -> AbortUploadResponse:
        """Abort a caller-owned multipart upload."""
        ...

    async def presign_download(
        self,
        request: PresignDownloadRequest,
        principal: Principal,
    ) -> PresignDownloadResponse:
        """Presign a scoped download for the authenticated principal."""
        ...


class TransferStorageClient(Protocol):
    """Async storage client contract used by the public transfer factory."""

    async def generate_presigned_url(self, **kwargs: Any) -> str:
        """Generate a presigned S3 URL."""
        ...

    async def create_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        """Create a multipart upload."""
        ...

    async def complete_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        """Complete a multipart upload."""
        ...

    async def abort_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        """Abort a multipart upload."""
        ...

    async def head_object(self, **kwargs: Any) -> dict[str, Any]:
        """Read object metadata."""
        ...

    async def list_parts(self, **kwargs: Any) -> dict[str, Any]:
        """List uploaded multipart parts."""
        ...

    async def copy_object(self, **kwargs: Any) -> dict[str, Any]:
        """Copy an object."""
        ...

    async def upload_part_copy(self, **kwargs: Any) -> dict[str, Any]:
        """Copy a multipart upload part."""
        ...


def _settings_from_transfer_config(config: TransferConfig) -> Settings:
    """Materialize runtime settings from an explicit transfer config."""
    return Settings.model_construct(
        file_transfer_enabled=config.enabled,
        file_transfer_bucket=config.bucket,
        file_transfer_upload_prefix=config.upload_prefix,
        file_transfer_export_prefix=config.export_prefix,
        file_transfer_tmp_prefix=config.tmp_prefix,
        file_transfer_presign_upload_ttl_seconds=(
            config.presign_upload_ttl_seconds
        ),
        file_transfer_presign_download_ttl_seconds=(
            config.presign_download_ttl_seconds
        ),
        file_transfer_multipart_threshold_bytes=(
            config.multipart_threshold_bytes
        ),
        file_transfer_part_size_bytes=config.part_size_bytes,
        file_transfer_max_concurrency=config.max_concurrency,
        file_transfer_use_accelerate_endpoint=config.use_accelerate_endpoint,
        max_upload_bytes=config.max_upload_bytes,
    )


def build_transfer_service(
    *,
    config: TransferConfig,
    s3_client: TransferStorageClient,
) -> AsyncTransferService:
    """Build the canonical async transfer service for adapter consumers."""
    return TransferService(
        settings=_settings_from_transfer_config(config),
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
    "AsyncTransferService",
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
    "TransferConfig",
    "TransferStorageClient",
    "UploadIntrospectionRequest",
    "UploadIntrospectionResponse",
    "UploadStrategy",
    "UploadedPart",
    "build_transfer_service",
]
