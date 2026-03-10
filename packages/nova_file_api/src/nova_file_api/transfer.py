"""S3 transfer orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

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
        """
        Create a TransferService configured with runtime settings and a prebuilt async S3 client.
        
        Parameters:
            settings (Settings): Configuration controlling upload/export/tmp prefixes and transfer behavior.
            s3_client (Any): Preconfigured async-capable S3 client used for all S3 operations.
        """
        self.settings = settings
        self._s3 = cast(Any, s3_client)
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
        """
        Start an upload by allocating an S3 key and returning either a single-part or multipart upload initiation response.
        
        Parameters:
            request (InitiateUploadRequest): Contains filename, size_bytes, and optional content_type used to select upload strategy and build the upload object.
            principal (Principal): Caller principal whose scope_id is used to construct the upload key.
        
        Returns:
            InitiateUploadResponse: Response describing the chosen upload strategy and S3 parameters (bucket/key and either a presigned put URL for single uploads or an upload_id, part size, and presign TTL for multipart).
        
        Raises:
            invalid_request: If request.size_bytes exceeds the configured max_upload_bytes.
        """
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
        """
        Generate presigned upload URLs for each multipart part for an upload key owned by the caller.
        
        Parameters:
            request (SignPartsRequest): Request containing `key`, `upload_id`, and `part_numbers` to sign.
            principal (Principal): Caller identity; `scope_id` is used to verify ownership of the upload key.
        
        Returns:
            SignPartsResponse: Contains `expires_in_seconds` and `urls`, a mapping from part number to its presigned upload URL.
        """
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

    async def complete_upload(
        self,
        request: CompleteUploadRequest,
        principal: Principal,
    ) -> CompleteUploadResponse:
        """
        Finalize a multipart upload for an upload key owned by the provided principal.
        
        Validates the caller's ownership of the key and completes the multipart upload identified by request.upload_id and request.parts.
        
        Returns:
            CompleteUploadResponse: The completed object's bucket and key, `etag` if present, and `version_id` if present.
        
        Raises:
            invalid_request: If the key is outside the caller's upload scope.
            upstream_s3_error: If the S3 complete multipart upload operation fails.
        """
        self._assert_upload_scope(key=request.key, scope_id=principal.scope_id)

        parts = [
            {"ETag": part.etag, "PartNumber": part.part_number}
            for part in sorted(request.parts, key=lambda item: item.part_number)
        ]

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
        """
        Abort a multipart upload owned by the caller.
        
        Validates that the provided key is within the caller's upload scope and aborts the multipart upload identified by the request's upload_id.
        
        Parameters:
        	request: Contains `key` (the object key to abort) and `upload_id` (the multipart upload ID).
        	principal: Caller principal whose `scope_id` is used to validate ownership of the upload key.
        
        Returns:
        	AbortUploadResponse: Response with `ok` set to True when the abort succeeds.
        
        Raises:
        	upstream_s3_error: If the underlying S3 abort operation fails.
        """
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
        """
        Create a presigned GET URL for a read-authorized object key.
        
        The response may include ResponseContentDisposition set from `request.content_disposition`
        (if provided) or constructed from `request.filename` (sanitized) as a fallback.
        If `request.content_type` is provided it is forwarded as ResponseContentType.
        The caller's `principal.scope_id` is validated against the key's allowed read scopes.
        
        Parameters:
            request: Uses `key`, optional `content_disposition`, optional `filename`, and optional `content_type`.
            principal: Caller principal whose `scope_id` is used for read-scope validation.
        
        Returns:
            PresignDownloadResponse: Contains bucket, key, a presigned GET URL, and `expires_in_seconds`.
        """
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
        """
        Copy an upload object from the caller's scoped upload prefix into the service's export prefix for a job.
        
        Parameters:
            source_bucket (str): Bucket containing the source upload object; must match configured transfer bucket.
            source_key (str): Key of the caller-scoped upload object to copy.
            scope_id (str): Caller scope identifier used for ownership validation.
            job_id (str): Job identifier used to namespace the export object key; sanitized if necessary.
            filename (str): Desired download filename to preserve with the exported object; falls back to the source object's basename.
        
        Returns:
            ExportCopyResult: Contains `export_key` (the destination key under the export prefix) and `download_filename` (sanitized filename to present to download consumers).
        
        Raises:
            FileTransferError: Raised via `invalid_request` when the source bucket does not match configuration, the source key is outside the caller's upload scope, or the source object is not found.
            FileTransferError: Raised via `upstream_s3_error` for S3-side errors that should be retried or investigated.
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
        await self._assert_upload_object_exists(key=source_key)
        download_filename = _sanitize_filename(
            filename or Path(source_key).name
        )
        export_key = self._new_export_key(
            scope_id=scope_id,
            job_id=job_id,
            filename=download_filename,
        )
        try:
            await self._s3.copy_object(
                Bucket=self.settings.file_transfer_bucket,
                CopySource={
                    "Bucket": self.settings.file_transfer_bucket,
                    "Key": source_key,
                },
                Key=export_key,
                MetadataDirective="COPY",
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
        """
        Create an initiation response for a single-object upload by generating a presigned PUT URL.
        
        Parameters:
            key (str): S3 object key where the file will be uploaded.
            content_type (str | None): Optional MIME type to associate with the uploaded object; included as Content-Type on the upload if provided.
        
        Returns:
            InitiateUploadResponse: Response containing UploadStrategy.SINGLE, the target bucket and key, a presigned PUT URL, and the URL's expiration in seconds.
        """
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
        """
        Initiates a multipart upload in S3 for the specified object key.
        
        Parameters:
            key (str): Object key for the multipart upload.
            content_type (str | None): Optional Content-Type to assign to the created object.
        
        Returns:
            InitiateUploadResponse: Initiation details including strategy `MULTIPART`, bucket, key,
            `upload_id`, configured `part_size_bytes`, and `expires_in_seconds`.
        
        Raises:
            upstream_s3_error: If the S3 create_multipart_upload call fails or the response lacks an UploadId.
        """
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
        """
        Generate a presigned S3 URL for the given client operation and parameters.
        
        Parameters:
            operation (str): S3 client method name to presign (e.g., "put_object", "get_object").
            params (dict[str, Any]): Parameters to pass to the S3 operation (Bucket, Key, etc.).
            expires_in (int): Number of seconds the presigned URL will remain valid.
        
        Returns:
            url (str): The generated presigned URL.
        
        Raises:
            upstream_s3_error: If the underlying S3 client fails to generate the presigned URL.
        """
        try:
            generated = await self._s3.generate_presigned_url(
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
        """
        Verify that the given S3 object key resides within the caller's upload scope.
        
        Parameters:
            key (str): The S3 object key to validate.
            scope_id (str): The caller's scope identifier used to determine the allowed upload prefix.
        
        Raises:
            InvalidRequestError: If the key does not start with the caller's upload scope prefix (raises with message "key is outside caller upload scope").
        """
        expected_prefix = f"{self._upload_prefix}{scope_id}/"
        if not key.startswith(expected_prefix):
            raise invalid_request("key is outside caller upload scope")

    def _assert_read_scope(self, *, key: str, scope_id: str) -> None:
        """
        Assert that `key` is readable by the caller identified by `scope_id`.
        
        This checks whether `key` starts with one of the service's readable prefixes for the given scope (upload, export, or tmp). If the key is not under any of those prefixes, an `invalid_request` error is raised.
        
        Parameters:
            key (str): S3 object key to validate.
            scope_id (str): Caller scope identifier used to construct allowed prefixes.
        
        Raises:
            invalid_request: If `key` is outside the caller's read scope (message: "key is outside caller read scope").
        """
        expected_prefixes = (
            f"{self._upload_prefix}{scope_id}/",
            f"{self._export_prefix}{scope_id}/",
            f"{self._tmp_prefix}{scope_id}/",
        )
        if not any(key.startswith(prefix) for prefix in expected_prefixes):
            raise invalid_request("key is outside caller read scope")

    async def _assert_upload_object_exists(self, *, key: str) -> None:
        """
        Verify that the specified object exists in the service's configured transfer S3 bucket.
        
        Parameters:
            key (str): S3 object key to check.
        
        Raises:
            invalid_request: If the object does not exist (S3 error code "404", "NoSuchKey", or "NotFound").
            upstream_s3_error: If an S3 or BotoCore error occurs while inspecting the object.
        """
        try:
            await self._s3.head_object(
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


def _sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to a safe basename containing only letters, digits, '.', '-', and '_' and truncated to at most 255 characters.
    
    Parameters:
        filename (str): A filename or path; only the basename portion is considered.
    
    Returns:
        sanitized_filename (str): The cleaned basename. If the cleaned name is empty, returns "file". If longer than 255 characters, the result is truncated to 255 characters.
    """
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