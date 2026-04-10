"""S3 transfer orchestration service."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.errors import (
    FileTransferError,
    invalid_request,
    too_many_requests,
    upstream_s3_error,
)
from nova_file_api.export_transfer import ExportCopyResult
from nova_file_api.export_utils import sanitize_filename
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
from nova_file_api.multipart_completion import (
    build_multipart_completion_payload,
)
from nova_file_api.s3_coercion import (
    normalize_prefix,
    opt_str,
    parse_non_negative_int,
    parse_positive_int,
)
from nova_file_api.transfer_config import TransferConfig
from nova_file_api.transfer_export_copy import ExportCopyCoordinator
from nova_file_api.transfer_policy import (
    TransferPolicy,
    TransferPolicyProvider,
    build_transfer_policy_provider,
    upload_part_size_bytes,
)
from nova_file_api.transfer_quota import TransferQuotaManager
from nova_file_api.transfer_sessions import UploadSessionLifecycle
from nova_file_api.transfer_usage import (
    TransferUsageWindowRepository,
    build_transfer_usage_window_repository,
)
from nova_file_api.upload_sessions import (
    UploadSessionRepository,
    UploadSessionStatus,
    UploadStrategy,
    build_upload_session_repository,
    new_upload_session_id,
)

_LOGGER = logging.getLogger(__name__)
_TRANSFER_HEALTHCHECK_CACHE_TTL_SECONDS = 10.0
_TRANSFER_HEALTHCHECK_TIMEOUT_SECONDS = 3.0


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
        self._session_lifecycle = UploadSessionLifecycle(self._upload_sessions)
        self._quota = TransferQuotaManager(self._transfer_usage)
        self._upload_prefix = normalize_prefix(self.config.upload_prefix)
        self._export_prefix = normalize_prefix(self.config.export_prefix)
        self._tmp_prefix = normalize_prefix(self.config.tmp_prefix)
        self._export_copy = ExportCopyCoordinator(
            config=config,
            s3_client=s3_client,
        )
        self._healthcheck_cached_result = False
        self._healthcheck_cached_until = 0.0
        self._healthcheck_lock = asyncio.Lock()

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
        await self._quota.reserve_upload(
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
                self._quota.release_upload_best_effort(
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
                await self._quota.release_upload_best_effort(
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
        session = await self._session_lifecycle.require_for_caller(
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
        # Per-upload sign quota is enforced above via ``sign_limit``. The usage
        # repository's hourly window tracks scope-level sign volume; there is no
        # distinct hourly cap in ``TransferPolicy`` today, so do not pass the
        # per-upload limit here (that would apply it incorrectly as an hourly
        # ceiling).
        await self._quota.record_sign_request(
            scope_id=principal.scope_id,
            sign_requested_at=now,
            hourly_sign_request_limit=None,
        )
        await self._session_lifecycle.store(
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
        session = await self._session_lifecycle.get_for_caller(
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
        await self._session_lifecycle.touch_if_present(
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
        session = await self._session_lifecycle.get_for_caller(
            upload_id=request.upload_id,
            scope_id=principal.scope_id,
            key=request.key,
        )
        uploaded_parts = await self._list_multipart_parts(
            key=request.key,
            upload_id=request.upload_id,
        )
        parts, expected_size_bytes = build_multipart_completion_payload(
            requested_parts=request.parts,
            uploaded_parts=uploaded_parts,
            session=session,
        )

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
            await self._session_lifecycle.store_best_effort(
                replace(
                    session,
                    status=UploadSessionStatus.COMPLETED,
                    last_activity_at=datetime.now(tz=UTC),
                )
            )
            await self._quota.release_upload_best_effort(
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
        session = await self._session_lifecycle.get_for_caller(
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
            await self._session_lifecycle.store_best_effort(
                replace(
                    session,
                    status=UploadSessionStatus.ABORTED,
                    last_activity_at=datetime.now(tz=UTC),
                )
            )
            await self._quota.release_upload_best_effort(
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
        return await self._export_copy.copy_upload_to_export(
            source_bucket=source_bucket,
            source_key=source_key,
            scope_id=scope_id,
            export_id=export_id,
            filename=filename,
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
        await self._session_lifecycle.store(
            self._session_lifecycle.new_record(
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
            await self._session_lifecycle.store(
                self._session_lifecycle.new_record(
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

    async def healthcheck(self) -> bool:
        """Return readiness for the transfer service dependencies."""
        cached_result = self._cached_healthcheck_result()
        if cached_result is not None:
            return cached_result

        async with self._healthcheck_lock:
            cached_result = self._cached_healthcheck_result()
            if cached_result is not None:
                return cached_result
            try:
                result = await asyncio.wait_for(
                    self._probe_transfer_dependencies(),
                    timeout=_TRANSFER_HEALTHCHECK_TIMEOUT_SECONDS,
                )
            except Exception:
                _LOGGER.warning(
                    "transfer_runtime_healthcheck_failed",
                    extra={"bucket": self.config.bucket},
                    exc_info=True,
                )
                result = False
            self._cache_healthcheck_result(result)
            return result

    async def _probe_transfer_dependencies(self) -> bool:
        bucket = self.config.bucket.strip()
        if not bucket:
            return False
        try:
            sessions_ready = await self._upload_sessions.healthcheck()
            usage_ready = await self._transfer_usage.healthcheck()
        except Exception:
            return False
        if not sessions_ready or not usage_ready:
            return False
        await self._s3.head_bucket(Bucket=bucket)
        return True

    def _cached_healthcheck_result(self) -> bool | None:
        if time.monotonic() >= self._healthcheck_cached_until:
            return None
        return self._healthcheck_cached_result

    def _cache_healthcheck_result(self, result: bool) -> None:
        self._healthcheck_cached_result = result
        self._healthcheck_cached_until = (
            time.monotonic() + _TRANSFER_HEALTHCHECK_CACHE_TTL_SECONDS
        )

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

    def _new_upload_key(self, *, scope_id: str, filename: str) -> str:
        safe = sanitize_filename(filename)
        return f"{self._upload_prefix}{scope_id}/{uuid4().hex}/{safe}"

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
