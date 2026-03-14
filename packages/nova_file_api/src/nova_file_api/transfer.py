"""S3 transfer orchestration service."""

from __future__ import annotations

import logging
import math
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.config import Settings
from nova_file_api.errors import (
    FileTransferError,
    invalid_request,
    upstream_s3_error,
)
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
    UploadedPart,
    UploadIntrospectionRequest,
    UploadIntrospectionResponse,
    UploadStrategy,
)

_COPY_OBJECT_MAX_BYTES = 5_000_000_000
_MAX_MULTIPART_PARTS = 10_000
_MIN_MULTIPART_PART_SIZE_BYTES = 5 * 1024 * 1024
_MAX_MULTIPART_PART_SIZE_BYTES = 5 * 1024 * 1024 * 1024
_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class ExportCopyResult:
    """Result returned after copying an upload object to the export prefix."""

    export_key: str
    download_filename: str


class TransferService:
    """Control-plane transfer service backed by async S3 calls."""

    def __init__(
        self,
        *,
        settings: Settings,
        s3_client: Any,
    ) -> None:
        """Initialize transfer service and S3 client.

        Args:
            settings: Runtime settings for transfer behavior.
            s3_client: Prebuilt async S3 client.
        """
        self.settings = settings
        self._s3 = s3_client
        self._upload_prefix = _normalize_prefix(
            self.settings.file_transfer_upload_prefix
        )
        self._export_prefix = _normalize_prefix(
            self.settings.file_transfer_export_prefix
        )
        self._tmp_prefix = _normalize_prefix(
            self.settings.file_transfer_tmp_prefix
        )

    async def initiate_upload(
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
            return await self._single_upload_response(
                key=key,
                content_type=request.content_type,
            )

        return await self._multipart_upload_response(
            key=key,
            content_type=request.content_type,
        )

    async def sign_parts(
        self,
        request: SignPartsRequest,
        principal: Principal,
    ) -> SignPartsResponse:
        """Sign multipart part URLs for caller-owned key."""
        self._assert_upload_scope(key=request.key, scope_id=principal.scope_id)

        urls: dict[int, str] = {}
        for part_number in request.part_numbers:
            urls[part_number] = await self._generate_presigned_url(
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

    async def introspect_upload(
        self,
        request: UploadIntrospectionRequest,
        principal: Principal,
    ) -> UploadIntrospectionResponse:
        """Return uploaded multipart part state for a caller-owned key.

        Args:
            request: Upload introspection request containing key and upload_id.
            principal: Authenticated principal for scope validation.

        Returns:
            UploadIntrospectionResponse: Multipart state including bucket, key,
                upload_id, part_size_bytes, and list of uploaded parts.

        Raises:
            FileTransferError: If scope validation fails or upload
                does not exist.
        """
        self._assert_upload_scope(key=request.key, scope_id=principal.scope_id)
        uploaded_parts = await self._list_multipart_parts(
            key=request.key,
            upload_id=request.upload_id,
        )
        part_size_bytes = (
            uploaded_parts[0][2]
            if uploaded_parts
            else self.settings.file_transfer_part_size_bytes
        )
        return UploadIntrospectionResponse(
            bucket=self.settings.file_transfer_bucket,
            key=request.key,
            upload_id=request.upload_id,
            part_size_bytes=part_size_bytes,
            parts=[
                UploadedPart(part_number=part_number, etag=etag)
                for part_number, etag, _size in uploaded_parts
            ],
        )

    async def complete_upload(
        self,
        request: CompleteUploadRequest,
        principal: Principal,
    ) -> CompleteUploadResponse:
        """Complete multipart upload for caller-owned key."""
        self._assert_upload_scope(key=request.key, scope_id=principal.scope_id)
        uploaded_parts = await self._list_multipart_parts(
            key=request.key,
            upload_id=request.upload_id,
        )
        uploaded_parts_by_number = {
            part_number: (etag, size_bytes)
            for part_number, etag, size_bytes in uploaded_parts
        }

        seen_part_numbers: set[int] = set()
        duplicate_part_numbers: set[int] = set()
        for part in request.parts:
            if part.part_number in seen_part_numbers:
                duplicate_part_numbers.add(part.part_number)
            seen_part_numbers.add(part.part_number)
        if duplicate_part_numbers:
            raise invalid_request(
                "multipart upload part numbers must be unique",
                details={"part_numbers": sorted(duplicate_part_numbers)},
            )

        parts = [
            {"ETag": part.etag, "PartNumber": part.part_number}
            for part in sorted(request.parts, key=lambda item: item.part_number)
        ]
        expected_size_bytes = 0
        for part in request.parts:
            uploaded = uploaded_parts_by_number.get(part.part_number)
            if uploaded is None:
                raise invalid_request(
                    "multipart upload part is missing",
                    details={"part_number": part.part_number},
                )
            uploaded_etag, size_bytes = uploaded
            if _normalize_etag(uploaded_etag) != _normalize_etag(part.etag):
                raise invalid_request(
                    "multipart upload part etag mismatch",
                    details={"part_number": part.part_number},
                )
            expected_size_bytes += size_bytes

        try:
            result = await self._s3.complete_multipart_upload(
                Bucket=self.settings.file_transfer_bucket,
                Key=request.key,
                UploadId=request.upload_id,
                MultipartUpload={"Parts": parts},
            )
        except (ClientError, BotoCoreError) as exc:
            raise upstream_s3_error(
                "failed to complete multipart upload"
            ) from exc
        # Multipart completion is already committed when S3 returns success.
        # Keep this verification best-effort so flaky read-after-complete checks
        # do not turn a successful completion into a retry-unsafe error.
        try:
            completed_object = await self._head_object(
                bucket=self.settings.file_transfer_bucket,
                key=request.key,
                missing_message="completed multipart upload object not found",
                failure_message="failed to inspect completed multipart upload",
            )
            content_length = _require_non_negative_int(
                completed_object.get("ContentLength"),
                error_message=(
                    "completed multipart upload is missing content length"
                ),
            )
            if content_length != expected_size_bytes:
                raise upstream_s3_error(
                    "completed multipart upload size did not match "
                    "uploaded parts"
                )
        except FileTransferError:
            _LOGGER.warning(
                "multipart_completion_verification_failed",
                extra={
                    "bucket": self.settings.file_transfer_bucket,
                    "key": request.key,
                    "expected_size_bytes": expected_size_bytes,
                },
                exc_info=True,
            )

        return CompleteUploadResponse(
            bucket=self.settings.file_transfer_bucket,
            key=request.key,
            etag=_opt_str(result.get("ETag")),
            version_id=_opt_str(result.get("VersionId")),
        )

    async def abort_upload(
        self,
        request: AbortUploadRequest,
        principal: Principal,
    ) -> AbortUploadResponse:
        """Abort multipart upload for caller-owned key."""
        self._assert_upload_scope(key=request.key, scope_id=principal.scope_id)

        try:
            await self._s3.abort_multipart_upload(
                Bucket=self.settings.file_transfer_bucket,
                Key=request.key,
                UploadId=request.upload_id,
            )
        except (ClientError, BotoCoreError) as exc:
            raise upstream_s3_error("failed to abort multipart upload") from exc

        return AbortUploadResponse(ok=True)

    async def presign_download(
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

        url = await self._generate_presigned_url(
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

    async def copy_upload_to_export(
        self,
        *,
        source_bucket: str,
        source_key: str,
        scope_id: str,
        job_id: str,
        filename: str,
    ) -> ExportCopyResult:
        """Copy a caller-scoped upload object into the export prefix.

        Args:
            source_bucket: Bucket containing the upload object to export.
            source_key: Caller-scoped upload object key to copy.
            scope_id: Caller scope identifier used for ownership validation.
            job_id: Job identifier used to namespace the export object key.
            filename: Download filename to preserve in the export result.

        Returns:
            ExportCopyResult: Metadata describing the copied export object.

        Raises:
            FileTransferError: ``invalid_request`` when caller validation or
                source object absence/TOCTOU checks fail.
            FileTransferError: ``upstream_s3_error`` for retryable S3
                infra failures.
        """
        if source_bucket != self.settings.file_transfer_bucket:
            raise invalid_request(
                "bucket does not match configured transfer bucket",
                details={
                    "bucket": source_bucket,
                    "expected_bucket": self.settings.file_transfer_bucket,
                },
            )
        self._assert_upload_scope(key=source_key, scope_id=scope_id)
        source_object = await self._head_object(
            bucket=self.settings.file_transfer_bucket,
            key=source_key,
            missing_message="source upload object not found",
            failure_message="failed to inspect source upload object",
        )
        download_filename = _sanitize_filename(
            filename or Path(source_key).name
        )
        export_key = self._new_export_key(
            scope_id=scope_id,
            job_id=job_id,
            filename=download_filename,
        )
        source_size_bytes = _require_non_negative_int(
            source_object.get("ContentLength"),
            error_message="source upload object is missing content length",
        )
        try:
            if source_size_bytes <= _COPY_OBJECT_MAX_BYTES:
                await self._s3.copy_object(
                    Bucket=self.settings.file_transfer_bucket,
                    CopySource={
                        "Bucket": self.settings.file_transfer_bucket,
                        "Key": source_key,
                    },
                    Key=export_key,
                    MetadataDirective="COPY",
                )
            else:
                await self._multipart_copy_upload_to_export(
                    source_key=source_key,
                    export_key=export_key,
                    source_size_bytes=source_size_bytes,
                    source_object=source_object,
                )
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise invalid_request("source upload object not found") from exc
            raise upstream_s3_error(
                "failed to copy upload object to export key"
            ) from exc
        except BotoCoreError as exc:
            raise upstream_s3_error(
                "failed to copy upload object to export key"
            ) from exc
        return ExportCopyResult(
            export_key=export_key,
            download_filename=download_filename,
        )

    async def _single_upload_response(
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

        url = await self._generate_presigned_url(
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

    async def _multipart_upload_response(
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
            output = await self._s3.create_multipart_upload(**kwargs)
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

    async def _generate_presigned_url(
        self,
        *,
        operation: str,
        params: dict[str, Any],
        expires_in: int,
    ) -> str:
        try:
            generated = await self._s3.generate_presigned_url(
                ClientMethod=operation,
                Params=params,
                ExpiresIn=expires_in,
            )
            return cast(str, generated)
        except (ClientError, BotoCoreError) as exc:
            raise upstream_s3_error("failed to generate presigned URL") from exc

    async def _list_multipart_parts(
        self,
        *,
        key: str,
        upload_id: str,
    ) -> list[tuple[int, str, int]]:
        parts: list[tuple[int, str, int]] = []
        part_number_marker: int | None = None
        while True:
            kwargs: dict[str, Any] = {
                "Bucket": self.settings.file_transfer_bucket,
                "Key": key,
                "UploadId": upload_id,
                "MaxParts": 1000,
            }
            if part_number_marker is not None:
                kwargs["PartNumberMarker"] = part_number_marker
            try:
                response = await self._s3.list_parts(**kwargs)
            except ClientError as exc:
                error_code = str(exc.response.get("Error", {}).get("Code", ""))
                if error_code in {"404", "NoSuchUpload", "NotFound"}:
                    raise invalid_request(
                        "multipart upload was not found"
                    ) from exc
                raise upstream_s3_error(
                    "failed to inspect multipart upload parts"
                ) from exc
            except BotoCoreError as exc:
                raise upstream_s3_error(
                    "failed to inspect multipart upload parts"
                ) from exc

            raw_parts = response.get("Parts")
            if isinstance(raw_parts, list):
                for raw_part in raw_parts:
                    if not isinstance(raw_part, dict):
                        continue
                    part_number = _require_positive_int(
                        raw_part.get("PartNumber"),
                        error_message=(
                            "multipart upload part is missing part number"
                        ),
                    )
                    etag = _opt_str(raw_part.get("ETag"))
                    if etag is None:
                        raise upstream_s3_error(
                            "multipart upload part is missing etag"
                        )
                    size_bytes = _require_non_negative_int(
                        raw_part.get("Size"),
                        error_message="multipart upload part is missing size",
                    )
                    parts.append((part_number, etag, size_bytes))

            if not response.get("IsTruncated"):
                break
            part_number_marker = _require_positive_int(
                response.get("NextPartNumberMarker"),
                error_message=(
                    "multipart upload pagination is missing next part marker"
                ),
            )
        return sorted(parts, key=lambda item: item[0])

    async def _head_object(
        self,
        *,
        bucket: str,
        key: str,
        missing_message: str,
        failure_message: str,
    ) -> dict[str, Any]:
        try:
            output = await self._s3.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise invalid_request(missing_message) from exc
            raise upstream_s3_error(failure_message) from exc
        except BotoCoreError as exc:
            raise upstream_s3_error(failure_message) from exc
        return cast(dict[str, Any], output)

    async def _multipart_copy_upload_to_export(
        self,
        *,
        source_key: str,
        export_key: str,
        source_size_bytes: int,
        source_object: dict[str, Any],
    ) -> None:
        upload_id: str | None = None
        part_size_bytes = _multipart_copy_part_size_bytes(
            source_size_bytes=source_size_bytes,
            preferred_part_size_bytes=self.settings.file_transfer_part_size_bytes,
        )
        try:
            create_upload_kwargs = _multipart_copy_create_upload_kwargs(
                bucket=self.settings.file_transfer_bucket,
                key=export_key,
                source_object=source_object,
            )
            output = await self._s3.create_multipart_upload(
                **create_upload_kwargs
            )
            upload_id = _opt_str(output.get("UploadId"))
            if upload_id is None:
                raise upstream_s3_error(
                    "multipart export copy response missing upload id"
                )

            completed_parts: list[dict[str, Any]] = []
            part_number = 1
            start_byte = 0
            while start_byte < source_size_bytes:
                end_byte = min(
                    source_size_bytes - 1,
                    start_byte + part_size_bytes - 1,
                )
                response = await self._s3.upload_part_copy(
                    Bucket=self.settings.file_transfer_bucket,
                    CopySource={
                        "Bucket": self.settings.file_transfer_bucket,
                        "Key": source_key,
                    },
                    CopySourceRange=f"bytes={start_byte}-{end_byte}",
                    Key=export_key,
                    PartNumber=part_number,
                    UploadId=upload_id,
                )
                completed_parts.append(
                    {
                        "ETag": _copy_part_etag(response),
                        "PartNumber": part_number,
                    }
                )
                start_byte = end_byte + 1
                part_number += 1

            await self._s3.complete_multipart_upload(
                Bucket=self.settings.file_transfer_bucket,
                Key=export_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": completed_parts},
            )
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if upload_id is not None:
                with suppress(ClientError, BotoCoreError):
                    await self._s3.abort_multipart_upload(
                        Bucket=self.settings.file_transfer_bucket,
                        Key=export_key,
                        UploadId=upload_id,
                    )
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise invalid_request("source upload object not found") from exc
            raise upstream_s3_error(
                "failed to copy upload object to export key"
            ) from exc
        except BotoCoreError as exc:
            if upload_id is not None:
                with suppress(ClientError, BotoCoreError):
                    await self._s3.abort_multipart_upload(
                        Bucket=self.settings.file_transfer_bucket,
                        Key=export_key,
                        UploadId=upload_id,
                    )
            raise upstream_s3_error(
                "failed to copy upload object to export key"
            ) from exc

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
        """Build an export object key for a pre-sanitized download filename."""
        stable_job_id = "".join(
            character
            for character in job_id.strip()
            if character.isalnum() or character in {"-", "_"}
        )
        if not stable_job_id:
            stable_job_id = uuid4().hex
        return f"{self._export_prefix}{scope_id}/{stable_job_id}/{filename}"

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


def _normalize_etag(value: str) -> str:
    return value.strip().strip('"')


def _require_positive_int(value: Any, *, error_message: str) -> int:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            parsed = 0
        if parsed > 0:
            return parsed
    raise upstream_s3_error(error_message)


def _require_non_negative_int(value: Any, *, error_message: str) -> int:
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            parsed = -1
        if parsed >= 0:
            return parsed
    raise upstream_s3_error(error_message)


def _copy_part_etag(response: dict[str, Any]) -> str:
    copy_result = response.get("CopyPartResult")
    if not isinstance(copy_result, dict):
        raise upstream_s3_error("multipart export copy part result is missing")
    etag = _opt_str(copy_result.get("ETag"))
    if etag is None:
        raise upstream_s3_error("multipart export copy part etag is missing")
    return etag


def _multipart_copy_part_size_bytes(
    *,
    source_size_bytes: int,
    preferred_part_size_bytes: int,
) -> int:
    return min(
        _MAX_MULTIPART_PART_SIZE_BYTES,
        max(
            preferred_part_size_bytes,
            _MIN_MULTIPART_PART_SIZE_BYTES,
            math.ceil(source_size_bytes / _MAX_MULTIPART_PARTS),
        ),
    )


def _multipart_copy_create_upload_kwargs(
    *,
    bucket: str,
    key: str,
    source_object: dict[str, Any],
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"Bucket": bucket, "Key": key}
    for field in (
        "CacheControl",
        "ContentDisposition",
        "ContentEncoding",
        "ContentLanguage",
        "ContentType",
        "Expires",
        "Metadata",
    ):
        value = source_object.get(field)
        if value is not None:
            kwargs[field] = value
    return kwargs
