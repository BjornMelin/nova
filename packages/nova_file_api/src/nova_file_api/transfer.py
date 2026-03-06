"""S3 transfer orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.config import Settings
from nova_file_api.errors import invalid_request, upstream_s3_error
from nova_file_api.models import (
    AbortUploadRequest,
    AbortUploadResponse,
    CompleteUploadRequest,
    CompleteUploadResponse,
    InitiateUploadRequest,
    InitiateUploadResponse,
    PresignDownloadRequest,
    PresignDownloadResponse,
    Principal,
    SignPartsRequest,
    SignPartsResponse,
    UploadStrategy,
)


class TransferService:
    """Control-plane transfer service backed by boto3 presign calls."""

    def __init__(
        self,
        *,
        settings: Settings,
        s3_client: Any | None = None,
    ) -> None:
        """Initialize transfer service and S3 client.

        Args:
            settings: Runtime settings for transfer behavior.
            s3_client: Optional prebuilt S3 client override.
        """
        self.settings = settings
        self._s3 = (
            cast(BaseClient, s3_client)
            if s3_client is not None
            else _build_s3_client(settings=self.settings)
        )
        self._upload_prefix = _normalize_prefix(
            self.settings.file_transfer_upload_prefix
        )
        self._export_prefix = _normalize_prefix(
            self.settings.file_transfer_export_prefix
        )
        self._tmp_prefix = _normalize_prefix(
            self.settings.file_transfer_tmp_prefix
        )

    def initiate_upload(
        self,
        request: InitiateUploadRequest,
        principal: Principal,
    ) -> InitiateUploadResponse:
        """Initiate single or multipart upload based on policy."""
        if request.size_bytes > self.settings.max_upload_bytes:
            raise invalid_request(
                "file size exceeds configured upload limit",
                details={
                    "size_bytes": request.size_bytes,
                    "max_upload_bytes": self.settings.max_upload_bytes,
                },
            )

        key = self._new_upload_key(
            scope_id=principal.scope_id,
            filename=request.filename,
        )

        if (
            request.size_bytes
            < self.settings.file_transfer_multipart_threshold_bytes
        ):
            return self._single_upload_response(
                key=key,
                content_type=request.content_type,
            )

        return self._multipart_upload_response(
            key=key,
            content_type=request.content_type,
        )

    def sign_parts(
        self,
        request: SignPartsRequest,
        principal: Principal,
    ) -> SignPartsResponse:
        """Sign multipart part URLs for caller-owned key."""
        self._assert_upload_scope(key=request.key, scope_id=principal.scope_id)

        urls: dict[int, str] = {}
        for part_number in request.part_numbers:
            urls[part_number] = self._generate_presigned_url(
                operation="upload_part",
                params={
                    "Bucket": self.settings.file_transfer_bucket,
                    "Key": request.key,
                    "UploadId": request.upload_id,
                    "PartNumber": part_number,
                },
                expires_in=(
                    self.settings.file_transfer_presign_upload_ttl_seconds
                ),
            )

        return SignPartsResponse(
            expires_in_seconds=(
                self.settings.file_transfer_presign_upload_ttl_seconds
            ),
            urls=urls,
        )

    def complete_upload(
        self,
        request: CompleteUploadRequest,
        principal: Principal,
    ) -> CompleteUploadResponse:
        """Complete multipart upload for caller-owned key."""
        self._assert_upload_scope(key=request.key, scope_id=principal.scope_id)

        parts = [
            {"ETag": part.etag, "PartNumber": part.part_number}
            for part in sorted(request.parts, key=lambda item: item.part_number)
        ]

        try:
            result = self._s3.complete_multipart_upload(
                Bucket=self.settings.file_transfer_bucket,
                Key=request.key,
                UploadId=request.upload_id,
                MultipartUpload={"Parts": parts},
            )
        except (ClientError, BotoCoreError) as exc:
            raise upstream_s3_error(
                "failed to complete multipart upload"
            ) from exc

        return CompleteUploadResponse(
            bucket=self.settings.file_transfer_bucket,
            key=request.key,
            etag=_opt_str(result.get("ETag")),
            version_id=_opt_str(result.get("VersionId")),
        )

    def abort_upload(
        self,
        request: AbortUploadRequest,
        principal: Principal,
    ) -> AbortUploadResponse:
        """Abort multipart upload for caller-owned key."""
        self._assert_upload_scope(key=request.key, scope_id=principal.scope_id)

        try:
            self._s3.abort_multipart_upload(
                Bucket=self.settings.file_transfer_bucket,
                Key=request.key,
                UploadId=request.upload_id,
            )
        except (ClientError, BotoCoreError) as exc:
            raise upstream_s3_error("failed to abort multipart upload") from exc

        return AbortUploadResponse(ok=True)

    def presign_download(
        self,
        request: PresignDownloadRequest,
        principal: Principal,
    ) -> PresignDownloadResponse:
        """Presign download URL for caller-owned key."""
        self._assert_read_scope(key=request.key, scope_id=principal.scope_id)

        params: dict[str, Any] = {
            "Bucket": self.settings.file_transfer_bucket,
            "Key": request.key,
        }
        # Precedence: explicit disposition first, then filename fallback.
        # Content type is independent.
        if request.content_disposition is not None:
            params["ResponseContentDisposition"] = request.content_disposition
        elif request.filename:
            params["ResponseContentDisposition"] = (
                f'attachment; filename="{_sanitize_filename(request.filename)}"'
            )
        if request.content_type is not None:
            params["ResponseContentType"] = request.content_type

        url = self._generate_presigned_url(
            operation="get_object",
            params=params,
            expires_in=self.settings.file_transfer_presign_download_ttl_seconds,
        )

        return PresignDownloadResponse(
            bucket=self.settings.file_transfer_bucket,
            key=request.key,
            url=url,
            expires_in_seconds=(
                self.settings.file_transfer_presign_download_ttl_seconds
            ),
        )

    def copy_upload_to_export(
        self,
        *,
        source_bucket: str,
        source_key: str,
        scope_id: str,
        job_id: str,
        filename: str,
    ) -> ExportCopyResult:
        """Copy a caller-scoped upload object into the export prefix."""
        if source_bucket != self.settings.file_transfer_bucket:
            raise invalid_request(
                "bucket does not match configured transfer bucket",
                details={
                    "bucket": source_bucket,
                    "expected_bucket": self.settings.file_transfer_bucket,
                },
            )
        self._assert_upload_scope(key=source_key, scope_id=scope_id)
        self._assert_upload_object_exists(key=source_key)
        download_filename = _sanitize_filename(
            filename or Path(source_key).name
        )
        export_key = self._new_export_key(
            scope_id=scope_id,
            job_id=job_id,
            filename=download_filename,
        )
        try:
            self._s3.copy_object(
                Bucket=self.settings.file_transfer_bucket,
                CopySource={
                    "Bucket": self.settings.file_transfer_bucket,
                    "Key": source_key,
                },
                Key=export_key,
                MetadataDirective="COPY",
            )
        except (ClientError, BotoCoreError) as exc:
            raise upstream_s3_error(
                "failed to copy upload object to export key"
            ) from exc
        return ExportCopyResult(
            export_key=export_key,
            download_filename=download_filename,
        )

    def _single_upload_response(
        self,
        *,
        key: str,
        content_type: str | None,
    ) -> InitiateUploadResponse:
        params: dict[str, Any] = {
            "Bucket": self.settings.file_transfer_bucket,
            "Key": key,
        }
        if content_type:
            params["ContentType"] = content_type

        url = self._generate_presigned_url(
            operation="put_object",
            params=params,
            expires_in=self.settings.file_transfer_presign_upload_ttl_seconds,
        )

        return InitiateUploadResponse(
            strategy=UploadStrategy.SINGLE,
            bucket=self.settings.file_transfer_bucket,
            key=key,
            url=url,
            expires_in_seconds=(
                self.settings.file_transfer_presign_upload_ttl_seconds
            ),
        )

    def _multipart_upload_response(
        self,
        *,
        key: str,
        content_type: str | None,
    ) -> InitiateUploadResponse:
        kwargs: dict[str, Any] = {
            "Bucket": self.settings.file_transfer_bucket,
            "Key": key,
        }
        if content_type:
            kwargs["ContentType"] = content_type
        try:
            output = self._s3.create_multipart_upload(**kwargs)
        except (ClientError, BotoCoreError) as exc:
            raise upstream_s3_error(
                "failed to initiate multipart upload"
            ) from exc

        upload_id = _opt_str(output.get("UploadId"))
        if upload_id is None:
            raise upstream_s3_error("S3 multipart response missing upload id")

        return InitiateUploadResponse(
            strategy=UploadStrategy.MULTIPART,
            bucket=self.settings.file_transfer_bucket,
            key=key,
            upload_id=upload_id,
            part_size_bytes=self.settings.file_transfer_part_size_bytes,
            expires_in_seconds=(
                self.settings.file_transfer_presign_upload_ttl_seconds
            ),
        )

    def _generate_presigned_url(
        self,
        *,
        operation: str,
        params: dict[str, Any],
        expires_in: int,
    ) -> str:
        try:
            generated = self._s3.generate_presigned_url(
                ClientMethod=operation,
                Params=params,
                ExpiresIn=expires_in,
            )
            return cast(str, generated)
        except (ClientError, BotoCoreError) as exc:
            raise upstream_s3_error("failed to generate presigned URL") from exc

    def _new_upload_key(self, *, scope_id: str, filename: str) -> str:
        safe = _sanitize_filename(filename)
        return f"{self._upload_prefix}{scope_id}/{uuid4().hex}/{safe}"

    def _new_export_key(
        self,
        *,
        scope_id: str,
        job_id: str,
        filename: str,
    ) -> str:
        safe = _sanitize_filename(filename)
        stable_job_id = "".join(
            character
            for character in job_id.strip()
            if character.isalnum() or character in {"-", "_"}
        )
        if not stable_job_id:
            stable_job_id = uuid4().hex
        return f"{self._export_prefix}{scope_id}/{stable_job_id}/{safe}"

    def _assert_upload_scope(self, *, key: str, scope_id: str) -> None:
        expected_prefix = f"{self._upload_prefix}{scope_id}/"
        if not key.startswith(expected_prefix):
            raise invalid_request("key is outside caller upload scope")

    def _assert_read_scope(self, *, key: str, scope_id: str) -> None:
        expected_prefixes = (
            f"{self._upload_prefix}{scope_id}/",
            f"{self._export_prefix}{scope_id}/",
            f"{self._tmp_prefix}{scope_id}/",
        )
        if not any(key.startswith(prefix) for prefix in expected_prefixes):
            raise invalid_request("key is outside caller read scope")

    def _assert_upload_object_exists(self, *, key: str) -> None:
        try:
            self._s3.head_object(
                Bucket=self.settings.file_transfer_bucket,
                Key=key,
            )
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise invalid_request("source upload object not found") from exc
            raise upstream_s3_error(
                "failed to inspect source upload object"
            ) from exc
        except BotoCoreError as exc:
            raise upstream_s3_error(
                "failed to inspect source upload object"
            ) from exc


@dataclass(slots=True, frozen=True)
class ExportCopyResult:
    """Result returned after copying an upload object to the export prefix."""

    export_key: str
    download_filename: str


def _build_s3_client(*, settings: Settings) -> BaseClient:
    accelerate_enabled = settings.file_transfer_use_accelerate_endpoint
    config = Config(s3={"use_accelerate_endpoint": accelerate_enabled})
    return boto3.client("s3", config=config)


def _sanitize_filename(filename: str) -> str:
    base_name = Path(filename).name
    cleaned = "".join(
        character
        for character in base_name
        if character.isalnum() or character in {".", "-", "_"}
    )
    if not cleaned:
        return "file"
    if len(cleaned) > 255:
        return cleaned[:255]
    return cleaned


def _normalize_prefix(prefix: str) -> str:
    normalized = prefix.strip()
    if not normalized:
        return ""
    if not normalized.endswith("/"):
        normalized = f"{normalized}/"
    return normalized


def _opt_str(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None
