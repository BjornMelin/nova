"""S3 transfer orchestration service."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.errors import (
    FileTransferError,
    invalid_request,
    session_store_unavailable,
    too_many_requests,
    upstream_s3_error,
)
from nova_file_api.export_transfer import ExportCopyResult
from nova_file_api.export_utils import (
    COPY_OBJECT_MAX_BYTES,
    build_export_object_key,
    multipart_copy_create_upload_kwargs,
    multipart_copy_part_size_bytes,
    sanitize_filename,
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
)
from nova_file_api.s3_coercion import (
    copy_part_etag,
    normalize_prefix,
    opt_str,
    parse_non_negative_int,
    parse_positive_int,
)
from nova_file_api.transfer_config import TransferConfig
from nova_file_api.transfer_policy import (
    TransferPolicy,
    TransferPolicyProvider,
    build_transfer_policy_provider,
    upload_part_size_bytes,
)
from nova_file_api.transfer_usage import (
    TransferQuotaExceeded,
    TransferUsageWindowRepository,
    build_transfer_usage_window_repository,
)
from nova_file_api.upload_sessions import (
    UploadSessionRecord,
    UploadSessionRepository,
    UploadSessionStatus,
    UploadStrategy,
    build_upload_session_repository,
    new_upload_session_id,
)

_LOGGER = logging.getLogger(__name__)


def _upstream_s3_err(message: str) -> Exception:
    return upstream_s3_error(message)


class TransferService:
    """Control-plane transfer service backed by async S3 calls."""

    def __init__(
        self,
        *,
        config: TransferConfig,
        s3_client: Any,
        accelerate_s3_client: Any | None = None,
        policy_provider: TransferPolicyProvider | None = None,
        upload_session_repository: UploadSessionRepository | None = None,
        transfer_usage_repository: TransferUsageWindowRepository | None = None,
    ) -> None:
        """Initialize transfer service and S3 client.

        Args:
            config: Transfer-specific runtime configuration.
            s3_client: Prebuilt async S3 client.
            accelerate_s3_client: Optional accelerate-mode S3 client used only
                when the effective transfer policy enables acceleration for
                presigned upload requests.
            policy_provider: Optional resolver for env/AppConfig transfer
                policy selection.
            upload_session_repository: Optional upload-session persistence
                backend used for durable multipart session state.
            transfer_usage_repository: Optional quota-window backend used for
                scope-level initiate/sign enforcement.
        """
        self.config = config
        self._s3 = s3_client
        self._accelerate_s3 = (
            accelerate_s3_client
            if accelerate_s3_client is not None
            else s3_client
        )
        self._policy_provider = (
            policy_provider
            if policy_provider is not None
            else build_transfer_policy_provider(config=config)
        )
        self._upload_sessions = (
            upload_session_repository
            if upload_session_repository is not None
            else build_upload_session_repository(
                table_name=self.config.upload_sessions_table,
                dynamodb_resource=None,
                enabled=bool(self.config.upload_sessions_table),
            )
        )
        self._transfer_usage = (
            transfer_usage_repository
            if transfer_usage_repository is not None
            else build_transfer_usage_window_repository(
                table_name=self.config.usage_table,
                dynamodb_resource=None,
                enabled=bool(self.config.usage_table),
            )
        )
        self._upload_prefix = normalize_prefix(self.config.upload_prefix)
        self._export_prefix = normalize_prefix(self.config.export_prefix)
        self._tmp_prefix = normalize_prefix(self.config.tmp_prefix)

    async def initiate_upload(
        self,
        request: InitiateUploadRequest,
        principal: Principal,
    ) -> InitiateUploadResponse:
        """Initiate single or multipart upload based on policy."""
        policy = await self.resolve_policy(
            scope_id=principal.scope_id,
            workload_class=request.workload_class,
            policy_hint=request.policy_hint,
            checksum_preference=request.checksum_preference,
        )
        if request.size_bytes > policy.max_upload_bytes:
            raise invalid_request(
                "file size exceeds configured upload limit",
                details={
                    "size_bytes": request.size_bytes,
                    "max_upload_bytes": policy.max_upload_bytes,
                },
            )

        created_at = datetime.now(tz=UTC)
        session_id = new_upload_session_id()
        key = self._new_upload_key(
            scope_id=principal.scope_id,
            filename=request.filename,
        )

        multipart = request.size_bytes >= policy.multipart_threshold_bytes
        await self._reserve_upload_quota(
            scope_id=principal.scope_id,
            created_at=created_at,
            size_bytes=request.size_bytes,
            multipart=multipart,
            policy=policy,
        )
        success = False
        released_after_failure = False
        try:
            if not multipart:
                result = await self._single_upload_response(
                    created_at=created_at,
                    session_id=session_id,
                    key=key,
                    content_type=request.content_type,
                    principal=principal,
                    request=request,
                    policy=policy,
                )
            else:
                result = await self._multipart_upload_response(
                    created_at=created_at,
                    session_id=session_id,
                    key=key,
                    content_type=request.content_type,
                    principal=principal,
                    request=request,
                    policy=policy,
                )
        except asyncio.CancelledError:
            # Await in `finally` can be cancelled with the task; shield so
            # quota release still runs before the caller observes cancellation.
            await asyncio.shield(
                self._release_upload_quota_best_effort(
                    scope_id=principal.scope_id,
                    created_at=created_at,
                    size_bytes=request.size_bytes,
                    multipart=multipart,
                    completed=False,
                )
            )
            released_after_failure = True
            raise
        else:
            success = True
            return result
        finally:
            if not success and not released_after_failure:
                await self._release_upload_quota_best_effort(
                    scope_id=principal.scope_id,
                    created_at=created_at,
                    size_bytes=request.size_bytes,
                    multipart=multipart,
                    completed=False,
                )

    async def sign_parts(
        self,
        request: SignPartsRequest,
        principal: Principal,
    ) -> SignPartsResponse:
        """Sign multipart part URLs for caller-owned key."""
        self._assert_upload_scope(key=request.key, scope_id=principal.scope_id)
        session = await self._require_upload_session(
            upload_id=request.upload_id,
            scope_id=principal.scope_id,
            key=request.key,
        )
        policy = await self.resolve_policy(scope_id=principal.scope_id)
        sign_batch_size_hint = (
            session.sign_batch_size_hint or policy.sign_batch_size_hint
        )
        if (
            sign_batch_size_hint > 0
            and len(request.part_numbers) > sign_batch_size_hint
        ):
            raise invalid_request(
                "requested part batch exceeds the current transfer policy",
                details={
                    "requested_parts": len(request.part_numbers),
                    "sign_batch_size_hint": sign_batch_size_hint,
                },
            )
        sign_limit = (
            session.sign_requests_limit or policy.sign_requests_per_upload_limit
        )
        next_sign_requests_count = session.sign_requests_count + 1
        if sign_limit is not None and next_sign_requests_count > sign_limit:
            raise too_many_requests(
                "sign-parts quota exceeded for this upload session",
                details={"limit": sign_limit},
            )
        now = datetime.now(tz=UTC)
        await self._record_sign_request(
            scope_id=principal.scope_id,
            sign_requested_at=now,
        )
        await self._store_upload_session(
            replace(
                session,
                sign_requests_count=next_sign_requests_count,
                status=UploadSessionStatus.ACTIVE,
                last_activity_at=now,
            )
        )

        async def presign_part(part_number: int) -> tuple[int, str]:
            params = {
                "Bucket": self.config.bucket,
                "Key": request.key,
                "UploadId": request.upload_id,
                "PartNumber": part_number,
            }
            if session.checksum_mode == "required":
                checksum_value = (request.checksums_sha256 or {}).get(
                    part_number
                )
                if checksum_value is None:
                    raise invalid_request(
                        (
                            "multipart checksum is required for this "
                            "upload session"
                        ),
                        details={"part_number": part_number},
                    )
                if session.checksum_algorithm == "SHA256":
                    params["ChecksumSHA256"] = checksum_value
            elif (
                session.checksum_algorithm == "SHA256"
                and request.checksums_sha256
                and part_number in request.checksums_sha256
            ):
                params["ChecksumSHA256"] = request.checksums_sha256[part_number]
            url = await self._generate_presigned_url(
                operation="upload_part",
                params=params,
                expires_in=self.config.presign_upload_ttl_seconds,
                s3_client=self._presign_s3_client(
                    use_accelerate_endpoint=session.accelerate_enabled
                ),
            )
            return part_number, url

        # Part batch size is capped above (sign_batch_size_hint); gather runs
        # presigns concurrently for latency without unbounded fan-out.
        pairs = await asyncio.gather(
            *[presign_part(on) for on in request.part_numbers]
        )
        urls = dict(pairs)

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

        parts: list[dict[str, Any]] = []
        for part in sorted(request.parts, key=lambda item: item.part_number):
            part_payload: dict[str, Any] = {
                "ETag": part.etag,
                "PartNumber": part.part_number,
            }
            if session is not None and session.checksum_mode == "required":
                if session.checksum_algorithm == "SHA256":
                    if part.checksum_sha256 is None:
                        raise invalid_request(
                            (
                                "multipart checksum is required for this "
                                "upload session"
                            ),
                            details={"part_number": part.part_number},
                        )
                    part_payload["ChecksumSHA256"] = part.checksum_sha256
            elif part.checksum_sha256 is not None:
                part_payload["ChecksumSHA256"] = part.checksum_sha256
            parts.append(part_payload)
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
            content_length = parse_non_negative_int(
                completed_object.get("ContentLength"),
                error_message=(
                    "completed multipart upload is missing content length"
                ),
                err=_upstream_s3_err,
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
            await self._release_upload_quota_best_effort(
                scope_id=session.scope_id,
                created_at=session.created_at,
                size_bytes=session.size_bytes,
                multipart=session.strategy == UploadStrategy.MULTIPART,
                completed=True,
            )

        return CompleteUploadResponse(
            bucket=self.config.bucket,
            key=request.key,
            etag=opt_str(result.get("ETag")),
            version_id=opt_str(result.get("VersionId")),
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
            await self._release_upload_quota_best_effort(
                scope_id=session.scope_id,
                created_at=session.created_at,
                size_bytes=session.size_bytes,
                multipart=session.strategy == UploadStrategy.MULTIPART,
                completed=False,
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
                f'attachment; filename="{sanitize_filename(request.filename)}"'
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
        download_filename = sanitize_filename(filename or Path(source_key).name)
        export_key = build_export_object_key(
            export_prefix=self._export_prefix,
            scope_id=scope_id,
            export_id=export_id,
            filename=download_filename,
        )
        source_size_bytes = parse_non_negative_int(
            source_object.get("ContentLength"),
            error_message="source upload object is missing content length",
            err=_upstream_s3_err,
        )
        try:
            if source_size_bytes <= COPY_OBJECT_MAX_BYTES:
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
        policy: TransferPolicy,
    ) -> InitiateUploadResponse:
        params: dict[str, Any] = {
            "Bucket": self.config.bucket,
            "Key": key,
        }
        if content_type:
            params["ContentType"] = content_type
        if policy.checksum_mode == "required":
            if policy.checksum_algorithm == "SHA256":
                checksum_value = request.checksum_value
                if checksum_value is None:
                    raise invalid_request(
                        (
                            "single-part checksum is required for this "
                            "transfer policy"
                        ),
                    )
                params["ChecksumSHA256"] = checksum_value
        elif (
            policy.checksum_algorithm == "SHA256"
            and request.checksum_value is not None
        ):
            params["ChecksumSHA256"] = request.checksum_value

        url = await self._generate_presigned_url(
            operation="put_object",
            params=params,
            expires_in=self.config.presign_upload_ttl_seconds,
            s3_client=self._presign_s3_client(
                use_accelerate_endpoint=policy.accelerate_enabled
            ),
        )
        resumable_until = created_at + timedelta(
            seconds=policy.resumable_ttl_seconds
        )
        response = InitiateUploadResponse(
            strategy=UploadStrategy.SINGLE,
            bucket=self.config.bucket,
            key=key,
            session_id=session_id,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            max_concurrency_hint=policy.max_concurrency_hint,
            sign_batch_size_hint=policy.sign_batch_size_hint,
            accelerate_enabled=policy.accelerate_enabled,
            checksum_algorithm=policy.checksum_algorithm,
            checksum_mode=policy.checksum_mode,
            resumable_until=resumable_until,
            url=url,
            expires_in_seconds=self.config.presign_upload_ttl_seconds,
        )
        await self._store_upload_session(
            self._new_upload_session_record(
                session_id=session_id,
                upload_id=None,
                key=key,
                strategy=UploadStrategy.SINGLE,
                part_size_bytes=None,
                created_at=created_at,
                principal=principal,
                request=request,
                policy=policy,
                resumable_until=resumable_until,
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
        policy: TransferPolicy,
    ) -> InitiateUploadResponse:
        kwargs: dict[str, Any] = {
            "Bucket": self.config.bucket,
            "Key": key,
        }
        if content_type:
            kwargs["ContentType"] = content_type
        if (
            policy.checksum_mode != "none"
            and policy.checksum_algorithm == "SHA256"
        ):
            kwargs["ChecksumAlgorithm"] = "SHA256"
        try:
            output = await self._presign_s3_client(
                use_accelerate_endpoint=policy.accelerate_enabled
            ).create_multipart_upload(**kwargs)
        except (ClientError, BotoCoreError) as exc:
            raise upstream_s3_error(
                "failed to initiate multipart upload"
            ) from exc

        upload_id = opt_str(output.get("UploadId"))
        if upload_id is None:
            raise upstream_s3_error("S3 multipart response missing upload id")
        part_size_bytes = upload_part_size_bytes(
            file_size_bytes=request.size_bytes,
            policy=policy,
        )
        resumable_until = created_at + timedelta(
            seconds=policy.resumable_ttl_seconds
        )
        response = InitiateUploadResponse(
            strategy=UploadStrategy.MULTIPART,
            bucket=self.config.bucket,
            key=key,
            session_id=session_id,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            max_concurrency_hint=policy.max_concurrency_hint,
            sign_batch_size_hint=policy.sign_batch_size_hint,
            accelerate_enabled=policy.accelerate_enabled,
            checksum_algorithm=policy.checksum_algorithm,
            checksum_mode=policy.checksum_mode,
            resumable_until=resumable_until,
            upload_id=upload_id,
            part_size_bytes=part_size_bytes,
            expires_in_seconds=self.config.presign_upload_ttl_seconds,
        )
        try:
            await self._store_upload_session(
                self._new_upload_session_record(
                    session_id=session_id,
                    upload_id=upload_id,
                    key=key,
                    strategy=UploadStrategy.MULTIPART,
                    part_size_bytes=part_size_bytes,
                    created_at=created_at,
                    principal=principal,
                    request=request,
                    policy=policy,
                    resumable_until=resumable_until,
                )
            )
        except FileTransferError:
            with suppress(ClientError, BotoCoreError):
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
        s3_client: Any | None = None,
    ) -> str:
        try:
            client = self._s3 if s3_client is None else s3_client
            generated = await client.generate_presigned_url(
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
                    part_number = parse_positive_int(
                        raw_part.get("PartNumber"),
                        error_message=(
                            "multipart upload part is missing part number"
                        ),
                        err=_upstream_s3_err,
                    )
                    etag = opt_str(raw_part.get("ETag"))
                    if etag is None:
                        raise upstream_s3_error(
                            "multipart upload part is missing etag"
                        )
                    size_bytes = parse_non_negative_int(
                        raw_part.get("Size"),
                        error_message="multipart upload part is missing size",
                        err=_upstream_s3_err,
                    )
                    parts.append((part_number, etag, size_bytes))

            if not response.get("IsTruncated"):
                break
            part_number_marker = parse_positive_int(
                response.get("NextPartNumberMarker"),
                error_message=(
                    "multipart upload pagination is missing next part marker"
                ),
                err=_upstream_s3_err,
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
        part_size_bytes = multipart_copy_part_size_bytes(
            source_size_bytes=source_size_bytes,
            preferred_part_size_bytes=self.config.export_copy_part_size_bytes,
        )
        try:
            create_upload_kwargs = multipart_copy_create_upload_kwargs(
                bucket=self.config.bucket,
                key=export_key,
                source_object=source_object,
            )
            output = await self._s3.create_multipart_upload(
                **create_upload_kwargs
            )
            upload_id = opt_str(output.get("UploadId"))
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
            "ETag": copy_part_etag(response, err=_upstream_s3_err),
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
            sessions_ready = await self._upload_sessions.healthcheck()
            usage_ready = await self._transfer_usage.healthcheck()
        except Exception:
            return False
        return sessions_ready and usage_ready

    async def resolve_policy(
        self,
        *,
        scope_id: str | None,
        workload_class: str | None = None,
        policy_hint: str | None = None,
        checksum_preference: str | None = None,
    ) -> TransferPolicy:
        """Return the effective transfer policy for one caller scope."""
        return await self._policy_provider.resolve(
            scope_id=scope_id,
            workload_class=workload_class,
            policy_hint=policy_hint,
            checksum_preference=checksum_preference,
        )

    def _presign_s3_client(self, *, use_accelerate_endpoint: bool) -> Any:
        return self._accelerate_s3 if use_accelerate_endpoint else self._s3

    async def _reserve_upload_quota(
        self,
        *,
        scope_id: str,
        created_at: datetime,
        size_bytes: int,
        multipart: bool,
        policy: TransferPolicy,
    ) -> None:
        try:
            await self._transfer_usage.reserve_upload(
                scope_id=scope_id,
                window_started_at=created_at,
                size_bytes=size_bytes,
                multipart=multipart,
                active_multipart_limit=policy.active_multipart_upload_limit,
                daily_ingress_budget_bytes=policy.daily_ingress_budget_bytes,
            )
        except TransferQuotaExceeded as exc:
            raise too_many_requests(
                "transfer quota exceeded for the current scope",
                details={"reason": exc.reason, **exc.details},
            ) from exc

    async def _release_upload_quota_best_effort(
        self,
        *,
        scope_id: str,
        created_at: datetime,
        size_bytes: int,
        multipart: bool,
        completed: bool,
    ) -> None:
        """Release quota; swallow and log failures.

        ``initiate_upload`` shields this coroutine on ``CancelledError``.
        """
        try:
            await self._transfer_usage.release_upload(
                scope_id=scope_id,
                window_started_at=created_at,
                size_bytes=size_bytes,
                multipart=multipart,
                completed=completed,
            )
        except Exception:
            _LOGGER.warning(
                "transfer_usage_release_failed",
                extra={
                    "scope_id": scope_id,
                    "size_bytes": size_bytes,
                    "multipart": multipart,
                    "completed": completed,
                },
                exc_info=True,
            )

    async def _record_sign_request(
        self,
        *,
        scope_id: str,
        sign_requested_at: datetime,
    ) -> None:
        try:
            await self._transfer_usage.record_sign_request(
                scope_id=scope_id,
                window_started_at=sign_requested_at,
                hourly_sign_request_limit=None,
            )
        except TransferQuotaExceeded as exc:
            raise too_many_requests(
                "sign-parts quota exceeded for the current scope",
                details={"reason": exc.reason, **exc.details},
            ) from exc

    def _new_upload_key(self, *, scope_id: str, filename: str) -> str:
        safe = sanitize_filename(filename)
        return f"{self._upload_prefix}{scope_id}/{uuid4().hex}/{safe}"

    def _new_upload_session_record(
        self,
        *,
        session_id: str,
        upload_id: str | None,
        key: str,
        strategy: UploadStrategy,
        part_size_bytes: int | None,
        created_at: datetime,
        principal: Principal,
        request: InitiateUploadRequest,
        policy: TransferPolicy,
        resumable_until: datetime,
    ) -> UploadSessionRecord:
        return UploadSessionRecord(
            session_id=session_id,
            upload_id=upload_id,
            scope_id=principal.scope_id,
            key=key,
            filename=request.filename,
            size_bytes=request.size_bytes,
            content_type=request.content_type,
            strategy=strategy,
            part_size_bytes=part_size_bytes,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            max_concurrency_hint=policy.max_concurrency_hint,
            sign_batch_size_hint=policy.sign_batch_size_hint,
            accelerate_enabled=policy.accelerate_enabled,
            checksum_algorithm=policy.checksum_algorithm,
            checksum_mode=policy.checksum_mode,
            sign_requests_count=0,
            sign_requests_limit=policy.sign_requests_per_upload_limit,
            resumable_until=resumable_until,
            resumable_until_epoch=int(resumable_until.timestamp()),
            status=UploadSessionStatus.INITIATED,
            request_id=None,
            created_at=created_at,
            last_activity_at=created_at,
        )

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


def _normalize_etag(value: str) -> str:
    return value.strip().strip('"')
