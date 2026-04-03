"""S3 transfer orchestration service."""

from __future__ import annotations

import asyncio
import logging
import math
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.errors import (
    FileTransferError,
    invalid_request,
    session_store_unavailable,
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
from nova_file_api.transfer_config import TransferConfig
from nova_file_api.upload_sessions import (
    UploadSessionRecord,
    UploadSessionRepository,
    UploadSessionStatus,
    build_upload_session_repository,
    new_upload_session_id,
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
        config: TransferConfig,
        s3_client: Any,
        upload_session_repository: UploadSessionRepository | None = None,
    ) -> None:
        """Initialize transfer service and S3 client.

        Args:
            config: Transfer-specific runtime configuration.
            s3_client: Prebuilt async S3 client.
            upload_session_repository: Optional upload-session persistence
                backend used for durable multipart session state.
        """
        self.config = config
        self._s3 = s3_client
        self._upload_sessions = (
            upload_session_repository
            if upload_session_repository is not None
            else build_upload_session_repository(
                table_name=self.config.upload_sessions_table,
                dynamodb_resource=None,
                enabled=bool(self.config.upload_sessions_table),
            )
        )
        self._upload_prefix = _normalize_prefix(self.config.upload_prefix)
        self._export_prefix = _normalize_prefix(self.config.export_prefix)
        self._tmp_prefix = _normalize_prefix(self.config.tmp_prefix)

    async def initiate_upload(
        self,
        request: InitiateUploadRequest,
        principal: Principal,
    ) -> InitiateUploadResponse:
        """Initiate single or multipart upload based on policy."""
        if request.size_bytes > self.config.max_upload_bytes:
            raise invalid_request(
                "file size exceeds configured upload limit",
                details={
                    "size_bytes": request.size_bytes,
                    "max_upload_bytes": self.config.max_upload_bytes,
                },
            )

        created_at = datetime.now(tz=UTC)
        session_id = new_upload_session_id()
        key = self._new_upload_key(
            scope_id=principal.scope_id,
            filename=request.filename,
        )

        if request.size_bytes < self.config.multipart_threshold_bytes:
            return await self._single_upload_response(
                created_at=created_at,
                session_id=session_id,
                key=key,
                content_type=request.content_type,
                principal=principal,
                request=request,
            )

        return await self._multipart_upload_response(
            created_at=created_at,
            session_id=session_id,
            key=key,
            content_type=request.content_type,
            principal=principal,
            request=request,
        )

    async def sign_parts(
        self,
        request: SignPartsRequest,
        principal: Principal,
    ) -> SignPartsResponse:
        """Sign multipart part URLs for caller-owned key."""
        self._assert_upload_scope(key=request.key, scope_id=principal.scope_id)
        await self._touch_upload_session_if_present(
            upload_id=request.upload_id,
            last_activity_at=datetime.now(tz=UTC),
            status=UploadSessionStatus.ACTIVE,
            scope_id=principal.scope_id,
            key=request.key,
        )

        urls: dict[int, str] = {}
        for part_number in request.part_numbers:
            urls[part_number] = await self._generate_presigned_url(
                operation="upload_part",
                params={
                    "Bucket": self.config.bucket,
                    "Key": request.key,
                    "UploadId": request.upload_id,
                    "PartNumber": part_number,
                },
                expires_in=self.config.presign_upload_ttl_seconds,
            )

        return SignPartsResponse(
            expires_in_seconds=self.config.presign_upload_ttl_seconds,
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
        session = await self._get_upload_session_for_caller(
            upload_id=request.upload_id,
            scope_id=principal.scope_id,
            key=request.key,
        )
        uploaded_parts = await self._list_multipart_parts(
            key=request.key,
            upload_id=request.upload_id,
        )
        part_size_bytes = (
            session.part_size_bytes
            if session is not None and session.part_size_bytes is not None
            else (
                uploaded_parts[0][2]
                if uploaded_parts
                else self.config.part_size_bytes
            )
        )
        await self._touch_upload_session_if_present(
            upload_id=request.upload_id,
            last_activity_at=datetime.now(tz=UTC),
            status=UploadSessionStatus.ACTIVE,
            scope_id=principal.scope_id,
            key=request.key,
        )
        return UploadIntrospectionResponse(
            bucket=self.config.bucket,
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
        session = await self._get_upload_session_for_caller(
            upload_id=request.upload_id,
            scope_id=principal.scope_id,
            key=request.key,
        )
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
                Bucket=self.config.bucket,
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
                bucket=self.config.bucket,
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
                    "bucket": self.config.bucket,
                    "key": request.key,
                    "expected_size_bytes": expected_size_bytes,
                },
                exc_info=True,
            )
        if session is not None:
            await self._store_upload_session_best_effort(
                replace(
                    session,
                    status=UploadSessionStatus.COMPLETED,
                    last_activity_at=datetime.now(tz=UTC),
                )
            )

        return CompleteUploadResponse(
            bucket=self.config.bucket,
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
        session = await self._get_upload_session_for_caller(
            upload_id=request.upload_id,
            scope_id=principal.scope_id,
            key=request.key,
        )

        try:
            await self._s3.abort_multipart_upload(
                Bucket=self.config.bucket,
                Key=request.key,
                UploadId=request.upload_id,
            )
        except (ClientError, BotoCoreError) as exc:
            raise upstream_s3_error("failed to abort multipart upload") from exc

        if session is not None:
            await self._store_upload_session_best_effort(
                replace(
                    session,
                    status=UploadSessionStatus.ABORTED,
                    last_activity_at=datetime.now(tz=UTC),
                )
            )

        return AbortUploadResponse(ok=True)

    async def presign_download(
        self,
        request: PresignDownloadRequest,
        principal: Principal,
    ) -> PresignDownloadResponse:
        """Presign download URL for caller-owned key."""
        self._assert_read_scope(key=request.key, scope_id=principal.scope_id)

        params: dict[str, Any] = {
            "Bucket": self.config.bucket,
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
            expires_in=self.config.presign_download_ttl_seconds,
        )

        return PresignDownloadResponse(
            bucket=self.config.bucket,
            key=request.key,
            url=url,
            expires_in_seconds=self.config.presign_download_ttl_seconds,
        )

    async def copy_upload_to_export(
        self,
        *,
        source_bucket: str,
        source_key: str,
        scope_id: str,
        export_id: str,
        filename: str,
    ) -> ExportCopyResult:
        """Copy a caller-scoped upload object into the export prefix.

        Args:
            source_bucket: Bucket containing the upload object to export.
            source_key: Caller-scoped upload object key to copy.
            scope_id: Caller scope identifier used for ownership validation.
            export_id: Export identifier used to namespace the export object
                key.
            filename: Download filename to preserve in the export result.

        Returns:
            ExportCopyResult: Metadata describing the copied export object.

        Raises:
            FileTransferError: ``invalid_request`` when caller validation or
                source object absence/TOCTOU checks fail.
            FileTransferError: ``upstream_s3_error`` for retryable S3
                infra failures.
        """
        if source_bucket != self.config.bucket:
            raise invalid_request(
                "bucket does not match configured transfer bucket",
                details={
                    "bucket": source_bucket,
                    "expected_bucket": self.config.bucket,
                },
            )
        self._assert_upload_scope(key=source_key, scope_id=scope_id)
        source_object = await self._head_object(
            bucket=self.config.bucket,
            key=source_key,
            missing_message="source upload object not found",
            failure_message="failed to inspect source upload object",
        )
        download_filename = _sanitize_filename(
            filename or Path(source_key).name
        )
        export_key = self._new_export_key(
            scope_id=scope_id,
            export_id=export_id,
            filename=download_filename,
        )
        source_size_bytes = _require_non_negative_int(
            source_object.get("ContentLength"),
            error_message="source upload object is missing content length",
        )
        try:
            if source_size_bytes <= _COPY_OBJECT_MAX_BYTES:
                await self._s3.copy_object(
                    Bucket=self.config.bucket,
                    CopySource={
                        "Bucket": self.config.bucket,
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
        created_at: datetime,
        session_id: str,
        key: str,
        content_type: str | None,
        principal: Principal,
        request: InitiateUploadRequest,
    ) -> InitiateUploadResponse:
        params: dict[str, Any] = {
            "Bucket": self.config.bucket,
            "Key": key,
        }
        if content_type:
            params["ContentType"] = content_type

        url = await self._generate_presigned_url(
            operation="put_object",
            params=params,
            expires_in=self.config.presign_upload_ttl_seconds,
        )
        resumable_until = self.config.resumable_until(created_at=created_at)
        response = InitiateUploadResponse(
            strategy=UploadStrategy.SINGLE,
            bucket=self.config.bucket,
            key=key,
            session_id=session_id,
            policy_id=self.config.policy_id,
            policy_version=self.config.policy_version,
            max_concurrency_hint=self.config.max_concurrency,
            sign_batch_size_hint=self.config.sign_batch_size_hint(),
            accelerate_enabled=self.config.use_accelerate_endpoint,
            checksum_algorithm=self.config.checksum_algorithm,
            resumable_until=resumable_until,
            url=url,
            expires_in_seconds=self.config.presign_upload_ttl_seconds,
        )
        await self._store_upload_session(
            UploadSessionRecord(
                session_id=session_id,
                upload_id=None,
                scope_id=principal.scope_id,
                key=key,
                filename=request.filename,
                size_bytes=request.size_bytes,
                content_type=request.content_type,
                strategy=UploadStrategy.SINGLE,
                part_size_bytes=None,
                policy_id=self.config.policy_id,
                policy_version=self.config.policy_version,
                max_concurrency_hint=self.config.max_concurrency,
                sign_batch_size_hint=self.config.sign_batch_size_hint(),
                accelerate_enabled=self.config.use_accelerate_endpoint,
                checksum_algorithm=self.config.checksum_algorithm,
                resumable_until=resumable_until,
                resumable_until_epoch=int(resumable_until.timestamp()),
                status=UploadSessionStatus.INITIATED,
                request_id=None,
                created_at=created_at,
                last_activity_at=created_at,
            )
        )
        return response

    async def _multipart_upload_response(
        self,
        *,
        created_at: datetime,
        session_id: str,
        key: str,
        content_type: str | None,
        principal: Principal,
        request: InitiateUploadRequest,
    ) -> InitiateUploadResponse:
        kwargs: dict[str, Any] = {
            "Bucket": self.config.bucket,
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
        part_size_bytes = self.config.upload_part_size_bytes(
            size_bytes=request.size_bytes
        )
        resumable_until = self.config.resumable_until(created_at=created_at)
        response = InitiateUploadResponse(
            strategy=UploadStrategy.MULTIPART,
            bucket=self.config.bucket,
            key=key,
            session_id=session_id,
            policy_id=self.config.policy_id,
            policy_version=self.config.policy_version,
            max_concurrency_hint=self.config.max_concurrency,
            sign_batch_size_hint=self.config.sign_batch_size_hint(),
            accelerate_enabled=self.config.use_accelerate_endpoint,
            checksum_algorithm=self.config.checksum_algorithm,
            resumable_until=resumable_until,
            upload_id=upload_id,
            part_size_bytes=part_size_bytes,
            expires_in_seconds=self.config.presign_upload_ttl_seconds,
        )
        try:
            await self._store_upload_session(
                UploadSessionRecord(
                    session_id=session_id,
                    upload_id=upload_id,
                    scope_id=principal.scope_id,
                    key=key,
                    filename=request.filename,
                    size_bytes=request.size_bytes,
                    content_type=request.content_type,
                    strategy=UploadStrategy.MULTIPART,
                    part_size_bytes=part_size_bytes,
                    policy_id=self.config.policy_id,
                    policy_version=self.config.policy_version,
                    max_concurrency_hint=self.config.max_concurrency,
                    sign_batch_size_hint=self.config.sign_batch_size_hint(),
                    accelerate_enabled=self.config.use_accelerate_endpoint,
                    checksum_algorithm=self.config.checksum_algorithm,
                    resumable_until=resumable_until,
                    resumable_until_epoch=int(resumable_until.timestamp()),
                    status=UploadSessionStatus.INITIATED,
                    request_id=None,
                    created_at=created_at,
                    last_activity_at=created_at,
                )
            )
        except Exception:
            with suppress(Exception):
                await self._s3.abort_multipart_upload(
                    Bucket=self.config.bucket,
                    Key=key,
                    UploadId=upload_id,
                )
            raise
        return response

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
                "Bucket": self.config.bucket,
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
            preferred_part_size_bytes=self.config.export_copy_part_size_bytes,
        )
        try:
            create_upload_kwargs = _multipart_copy_create_upload_kwargs(
                bucket=self.config.bucket,
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
            ranges = [
                (
                    part_number,
                    start_byte,
                    min(
                        source_size_bytes - 1,
                        start_byte + part_size_bytes - 1,
                    ),
                )
                for part_number, start_byte in enumerate(
                    range(0, source_size_bytes, part_size_bytes),
                    start=1,
                )
            ]
            copy_concurrency = min(
                self.config.export_copy_max_concurrency,
                self.config.max_concurrency,
            )
            for start_index in range(
                0,
                len(ranges),
                copy_concurrency,
            ):
                batch = ranges[start_index : start_index + copy_concurrency]
                completed_parts.extend(
                    await asyncio.gather(
                        *[
                            self._copy_multipart_export_part(
                                source_key=source_key,
                                export_key=export_key,
                                upload_id=upload_id,
                                part_number=part_number,
                                start_byte=start_byte,
                                end_byte=end_byte,
                            )
                            for part_number, start_byte, end_byte in batch
                        ]
                    )
                )

            await self._s3.complete_multipart_upload(
                Bucket=self.config.bucket,
                Key=export_key,
                UploadId=upload_id,
                MultipartUpload={
                    "Parts": sorted(
                        completed_parts,
                        key=lambda item: int(item["PartNumber"]),
                    )
                },
            )
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if upload_id is not None:
                with suppress(ClientError, BotoCoreError):
                    await self._s3.abort_multipart_upload(
                        Bucket=self.config.bucket,
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
                        Bucket=self.config.bucket,
                        Key=export_key,
                        UploadId=upload_id,
                    )
            raise upstream_s3_error(
                "failed to copy upload object to export key"
            ) from exc

    async def _copy_multipart_export_part(
        self,
        *,
        source_key: str,
        export_key: str,
        upload_id: str,
        part_number: int,
        start_byte: int,
        end_byte: int,
    ) -> dict[str, Any]:
        """Copy one multipart export range and return the completion payload."""
        response = await self._s3.upload_part_copy(
            Bucket=self.config.bucket,
            CopySource={
                "Bucket": self.config.bucket,
                "Key": source_key,
            },
            CopySourceRange=f"bytes={start_byte}-{end_byte}",
            Key=export_key,
            PartNumber=part_number,
            UploadId=upload_id,
        )
        return {
            "ETag": _copy_part_etag(response),
            "PartNumber": part_number,
        }

    async def _store_upload_session(
        self,
        record: UploadSessionRecord,
    ) -> None:
        try:
            await self._upload_sessions.create(record)
        except Exception as exc:
            _LOGGER.exception(
                "upload_session_store_failed",
                extra={
                    "session_id": record.session_id,
                    "upload_id": record.upload_id,
                    "scope_id": record.scope_id,
                },
            )
            raise session_store_unavailable(
                "upload session store is unavailable"
            ) from exc

    async def _get_upload_session(
        self,
        *,
        upload_id: str,
    ) -> UploadSessionRecord | None:
        try:
            return await self._upload_sessions.get_by_upload_id(
                upload_id=upload_id
            )
        except Exception as exc:
            _LOGGER.exception(
                "upload_session_lookup_failed",
                extra={"upload_id": upload_id},
            )
            raise session_store_unavailable(
                "upload session store is unavailable"
            ) from exc

    async def _store_upload_session_best_effort(
        self,
        record: UploadSessionRecord,
    ) -> None:
        try:
            await self._store_upload_session(record)
        except FileTransferError:
            _LOGGER.warning(
                "upload_session_store_best_effort_failed",
                extra={
                    "session_id": record.session_id,
                    "upload_id": record.upload_id,
                    "scope_id": record.scope_id,
                    "status": record.status.value,
                },
                exc_info=True,
            )

    async def _require_upload_session(
        self,
        *,
        upload_id: str,
        scope_id: str,
        key: str,
    ) -> UploadSessionRecord:
        session = await self._get_upload_session(upload_id=upload_id)
        if session is None:
            raise invalid_request("upload session was not found")
        if session.scope_id != scope_id or session.key != key:
            raise invalid_request("upload session is outside caller scope")
        return session

    async def _get_upload_session_for_caller(
        self,
        *,
        upload_id: str,
        scope_id: str,
        key: str,
    ) -> UploadSessionRecord | None:
        session = await self._get_upload_session(upload_id=upload_id)
        if session is None:
            return None
        if session.scope_id != scope_id or session.key != key:
            raise invalid_request("upload session is outside caller scope")
        return session

    async def _touch_upload_session(
        self,
        *,
        upload_id: str,
        last_activity_at: datetime,
        status: UploadSessionStatus,
        scope_id: str,
        key: str,
    ) -> None:
        session = await self._require_upload_session(
            upload_id=upload_id,
            scope_id=scope_id,
            key=key,
        )
        await self._store_upload_session(
            replace(
                session,
                status=status,
                last_activity_at=last_activity_at,
            )
        )

    async def _touch_upload_session_if_present(
        self,
        *,
        upload_id: str,
        last_activity_at: datetime,
        status: UploadSessionStatus,
        scope_id: str,
        key: str,
    ) -> None:
        session = await self._get_upload_session_for_caller(
            upload_id=upload_id,
            scope_id=scope_id,
            key=key,
        )
        if session is None:
            return
        try:
            await self._store_upload_session(
                replace(
                    session,
                    status=status,
                    last_activity_at=last_activity_at,
                )
            )
        except FileTransferError:
            _LOGGER.warning(
                "upload_session_touch_best_effort_failed",
                extra={
                    "upload_id": upload_id,
                    "scope_id": scope_id,
                    "key": key,
                    "status": status.value,
                },
                exc_info=True,
            )

    async def healthcheck(self) -> bool:
        """Return readiness for the transfer service dependencies."""
        try:
            return await self._upload_sessions.healthcheck()
        except Exception:
            return False

    def _new_upload_key(self, *, scope_id: str, filename: str) -> str:
        safe = _sanitize_filename(filename)
        return f"{self._upload_prefix}{scope_id}/{uuid4().hex}/{safe}"

    def _new_export_key(
        self,
        *,
        scope_id: str,
        export_id: str,
        filename: str,
    ) -> str:
        """Build an export object key for a pre-sanitized download filename."""
        stable_export_id = "".join(
            character
            for character in export_id.strip()
            if character.isalnum() or character in {"-", "_"}
        )
        if not stable_export_id:
            stable_export_id = uuid4().hex
        return f"{self._export_prefix}{scope_id}/{stable_export_id}/{filename}"

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
