"""Bridge services over the canonical Nova transfer runtime."""

from __future__ import annotations

import asyncio
import math
import re
import threading
from collections.abc import Awaitable, Callable
from contextlib import closing
from pathlib import Path
from typing import Any, TypeVar, cast
from urllib.parse import quote_from_bytes
from uuid import uuid4

from anyio import to_thread
from anyio.from_thread import BlockingPortalProvider
from botocore.exceptions import BotoCoreError, ClientError
from nova_file_api.public import (
    AbortUploadRequest,
    AbortUploadResponse,
    AsyncTransferService,
    CompleteUploadRequest,
    CompleteUploadResponse,
    InitiateUploadRequest,
    InitiateUploadResponse,
    PresignDownloadRequest,
    PresignDownloadResponse,
    Principal,
    SignPartsRequest,
    SignPartsResponse,
    TransferConfig,
    UploadIntrospectionRequest,
    UploadIntrospectionResponse,
    UploadStrategy,
    build_transfer_service,
)
from nova_file_api.public import FileTransferError as CoreFileTransferError

from nova_dash_bridge.config import (
    AuthPolicy,
    FileTransferEnvConfig,
    UploadPolicy,
)
from nova_dash_bridge.errors import (
    FileTransferError,
    conflict_error,
    internal_error,
    unauthorized_error,
    validation_error,
)
from nova_dash_bridge.s3_client import (
    S3Client,
    S3ClientFactory,
    SupportsCreateS3Client,
)

_INVALID_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_T = TypeVar("_T")


class _AsyncS3ClientAdapter:
    """Expose async S3 methods by delegating to a sync boto3 client."""

    def __init__(self, *, client: S3Client) -> None:
        self._client = client

    async def generate_presigned_url(self, **kwargs: Any) -> str:
        return str(
            await to_thread.run_sync(
                self._client.generate_presigned_url,
                **kwargs,
            )
        )

    async def create_multipart_upload(self, **kwargs: Any) -> dict[str, object]:
        return cast(
            dict[str, object],
            await to_thread.run_sync(
                self._client.create_multipart_upload,
                **kwargs,
            ),
        )

    async def complete_multipart_upload(
        self, **kwargs: Any
    ) -> dict[str, object]:
        return cast(
            dict[str, object],
            await to_thread.run_sync(
                self._client.complete_multipart_upload,
                **kwargs,
            ),
        )

    async def abort_multipart_upload(self, **kwargs: Any) -> dict[str, object]:
        return cast(
            dict[str, object],
            await to_thread.run_sync(
                self._client.abort_multipart_upload,
                **kwargs,
            ),
        )

    async def head_object(self, **kwargs: Any) -> dict[str, object]:
        return cast(
            dict[str, object],
            await to_thread.run_sync(self._client.head_object, **kwargs),
        )

    async def list_parts(self, **kwargs: Any) -> dict[str, object]:
        return cast(
            dict[str, object],
            await to_thread.run_sync(self._client.list_parts, **kwargs),
        )

    async def copy_object(self, **kwargs: Any) -> dict[str, object]:
        return cast(
            dict[str, object],
            await to_thread.run_sync(self._client.copy_object, **kwargs),
        )

    async def upload_part_copy(self, **kwargs: Any) -> dict[str, object]:
        return cast(
            dict[str, object],
            await to_thread.run_sync(self._client.upload_part_copy, **kwargs),
        )


class AsyncFileTransferService:
    """Async bridge service for FastAPI and other async hosts."""

    DEFAULT_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024

    def __init__(
        self,
        *,
        env_config: FileTransferEnvConfig,
        upload_policy: UploadPolicy,
        auth_policy: AuthPolicy,
        s3_client_factory: SupportsCreateS3Client | None = None,
    ) -> None:
        """Build the async bridge service from explicit bridge policies."""
        self._env = env_config
        self._policy = upload_policy
        self._auth = auth_policy
        self._factory = s3_client_factory or S3ClientFactory()
        self._core_config = _core_config_from_bridge(
            env_config=env_config,
            upload_policy=upload_policy,
        )
        self._core_service: AsyncTransferService | None = None
        self._core_service_lock = threading.Lock()

    @property
    def part_size_bytes(self) -> int:
        """Return the effective multipart part size."""
        return (
            self._policy.part_size_bytes
            if self._policy.part_size_bytes is not None
            else self._env.part_size_bytes
        )

    @property
    def multipart_threshold_bytes(self) -> int:
        """Return the size at which uploads switch to multipart mode."""
        return (
            self._policy.multipart_threshold_bytes
            if self._policy.multipart_threshold_bytes is not None
            else self._env.multipart_threshold_bytes
        )

    def ensure_enabled(self) -> None:
        """Fail closed when file transfer support is disabled or incomplete."""
        if not self._env.enabled:
            raise conflict_error("file transfer is not enabled")
        if not self._env.bucket:
            raise internal_error("FILE_TRANSFER_BUCKET is not configured")

    def _client(self) -> S3Client:
        return self._factory.create(self._env)

    @property
    def bucket(self) -> str:
        """Return the configured transfer bucket."""
        return self._env.bucket

    def create_s3_client(self) -> S3Client:
        """Create a sync S3 client for direct bridge operations."""
        return self._client()

    def _build_core_service(self) -> AsyncTransferService:
        service = self._core_service
        if service is not None:
            return service
        with self._core_service_lock:
            service = self._core_service
            if service is None:
                service = build_transfer_service(
                    config=self._core_config,
                    s3_client=_AsyncS3ClientAdapter(
                        client=self.create_s3_client()
                    ),
                )
                self._core_service = service
        return service

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Return a log-safe filename suitable for S3 object keys."""
        name = Path(filename).name
        stem = Path(name).stem.strip()
        ext = Path(name).suffix.lower()
        safe_stem = _INVALID_FILENAME_RE.sub("_", stem).strip("._")
        if not safe_stem:
            safe_stem = "upload"
        return f"{safe_stem}{ext}"

    @staticmethod
    def _coerce_prefix(prefix: str) -> str:
        raw = prefix.strip()
        if not raw:
            raise FileTransferError(
                code="validation_error",
                message=f"prefix must be non-empty: {prefix!r}",
                details={"prefix": prefix},
            )
        return raw if raw.endswith("/") else f"{raw}/"

    def resolve_principal(
        self,
        authorization_header: str | None,
    ) -> Principal:
        """Resolve a trusted principal from the incoming bearer header."""
        try:
            return self._auth.resolve_principal(authorization_header)
        except ValueError as exc:
            raise unauthorized_error(str(exc)) from exc

    def build_upload_key(self, *, scope_id: str, filename: str) -> str:
        """Build a scoped upload key for a caller-owned object."""
        safe_name = self.sanitize_filename(filename)
        prefix = self._coerce_prefix(self._env.upload_prefix)
        return f"{prefix}{scope_id}/{uuid4()}/{safe_name}"

    def build_export_key(self, *, scope_id: str, filename: str) -> str:
        """Build a scoped export key for a generated object."""
        safe_name = self.sanitize_filename(filename)
        prefix = self._coerce_prefix(self._env.export_prefix)
        return f"{prefix}{scope_id}/{uuid4()}/{safe_name}"

    def ensure_key_scoped(
        self,
        *,
        key: str,
        scope_id: str,
        allowed_prefix: str,
    ) -> None:
        """Validate that a key stays within the principal scope and prefix."""
        prefix = self._coerce_prefix(allowed_prefix)
        if not key.startswith(prefix):
            raise validation_error("key is outside the allowed prefix")
        scoped = f"{prefix}{scope_id}/"
        if not key.startswith(scoped):
            raise validation_error("key is outside the principal scope")

    def multipart_part_count(self, *, size_bytes: int) -> int:
        """Return the multipart part count for the given object size."""
        if size_bytes <= 0:
            return 1
        return math.ceil(size_bytes / float(self.part_size_bytes))

    def select_upload_strategy(self, *, size_bytes: int) -> str:
        """Select the upload strategy for the requested object size."""
        return (
            "multipart"
            if size_bytes >= self.multipart_threshold_bytes
            else "single"
        )

    def validate_upload_request(self, req: InitiateUploadRequest) -> None:
        """Enforce bridge upload constraints before presigning operations."""
        if req.size_bytes > self._policy.max_upload_bytes:
            raise validation_error("file exceeds maximum allowed upload size")
        ext = Path(req.filename).suffix.lower()
        if ext not in self._policy.allowed_extensions:
            allowed = sorted(self._policy.allowed_extensions)
            raise validation_error(
                "unsupported file extension",
                details={"allowed_extensions": allowed},
            )
        ext_cap = self._policy.per_extension_max_bytes.get(ext)
        if ext_cap is not None and req.size_bytes > ext_cap:
            raise validation_error(
                "file exceeds extension-specific size cap",
                details={"extension": ext, "max_bytes": ext_cap},
            )
        if (
            self.select_upload_strategy(size_bytes=req.size_bytes)
            == "multipart"
            and self.multipart_part_count(size_bytes=req.size_bytes) > 10_000
        ):
            raise validation_error("object too large for configured part size")

    async def initiate_upload(
        self,
        req: InitiateUploadRequest,
        principal: Principal,
    ) -> InitiateUploadResponse:
        """Initiate an upload via the canonical async Nova service."""
        self.ensure_enabled()
        self.validate_upload_request(req)
        core_response = await self._build_core_service().initiate_upload(
            req,
            principal,
        )
        if (
            core_response.strategy == UploadStrategy.SINGLE
            and core_response.url is None
        ):
            raise internal_error("missing presigned upload URL")
        if (
            core_response.strategy == UploadStrategy.MULTIPART
            and core_response.upload_id is None
        ):
            raise internal_error("missing multipart upload id")
        if (
            core_response.strategy == UploadStrategy.MULTIPART
            and core_response.part_size_bytes is None
        ):
            raise internal_error("missing multipart part size")
        return core_response

    async def sign_parts(
        self,
        req: SignPartsRequest,
        principal: Principal,
    ) -> SignPartsResponse:
        """Presign multipart part URLs via the canonical async service."""
        self.ensure_enabled()
        return await self._build_core_service().sign_parts(req, principal)

    async def introspect_upload(
        self,
        req: UploadIntrospectionRequest,
        principal: Principal,
    ) -> UploadIntrospectionResponse:
        """Return multipart upload state for a caller-owned key."""
        self.ensure_enabled()
        return await self._build_core_service().introspect_upload(
            req,
            principal,
        )

    async def complete_upload(
        self,
        req: CompleteUploadRequest,
        principal: Principal,
    ) -> CompleteUploadResponse:
        """Complete a caller-owned multipart upload."""
        self.ensure_enabled()
        return await self._build_core_service().complete_upload(req, principal)

    async def abort_upload(
        self,
        req: AbortUploadRequest,
        principal: Principal,
    ) -> AbortUploadResponse:
        """Abort a caller-owned multipart upload."""
        self.ensure_enabled()
        await self._build_core_service().abort_upload(req, principal)
        return AbortUploadResponse()

    @classmethod
    def _build_content_disposition(
        cls,
        *,
        content_disposition: str,
        filename: str,
    ) -> str:
        safe_name = cls.sanitize_filename(filename)
        clean_name = "".join(
            char for char in safe_name if 0x20 <= ord(char) <= 0x7E
        )
        escaped_name = clean_name.replace("\\", "\\\\").replace('"', '\\"')
        encoded_name = quote_from_bytes(safe_name.encode("utf-8"), safe="")
        return (
            f'{content_disposition}; filename="{escaped_name}"; '
            f"filename*=UTF-8''{encoded_name}"
        )

    async def presign_download(
        self,
        req: PresignDownloadRequest,
        principal: Principal,
    ) -> PresignDownloadResponse:
        """Presign a scoped download for an export object."""
        self.ensure_enabled()
        self.ensure_key_scoped(
            key=req.key,
            scope_id=principal.scope_id,
            allowed_prefix=self._env.export_prefix,
        )
        disposition: str | None
        if req.content_disposition is not None:
            disposition = req.content_disposition
        elif req.filename:
            disposition = self._build_content_disposition(
                content_disposition="attachment",
                filename=req.filename,
            )
        else:
            disposition = None
        return await self._build_core_service().presign_download(
            PresignDownloadRequest(
                key=req.key,
                content_disposition=disposition,
                filename=req.filename,
                content_type=req.content_type,
            ),
            principal,
        )


class FileTransferService:
    """Thin sync adapter over the async bridge service."""

    DEFAULT_MAX_DOWNLOAD_BYTES = (
        AsyncFileTransferService.DEFAULT_MAX_DOWNLOAD_BYTES
    )

    def __init__(
        self,
        *,
        env_config: FileTransferEnvConfig,
        upload_policy: UploadPolicy,
        auth_policy: AuthPolicy,
        s3_client_factory: SupportsCreateS3Client | None = None,
    ) -> None:
        """Build the explicit sync adapter for sync-only framework hosts."""
        self._async_service = AsyncFileTransferService(
            env_config=env_config,
            upload_policy=upload_policy,
            auth_policy=auth_policy,
            s3_client_factory=s3_client_factory,
        )
        self._portal_provider = BlockingPortalProvider()

    def _call_async(
        self,
        func: Callable[..., Awaitable[_T]],
        *args: object,
    ) -> _T:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            with self._portal_provider as portal:
                return portal.call(func, *args)
        raise RuntimeError(
            "FileTransferService sync methods cannot run inside an active "
            "event loop"
        )

    @property
    def part_size_bytes(self) -> int:
        """Return the effective multipart part size."""
        return self._async_service.part_size_bytes

    @property
    def multipart_threshold_bytes(self) -> int:
        """Return the size at which uploads switch to multipart mode."""
        return self._async_service.multipart_threshold_bytes

    def resolve_principal(
        self,
        authorization_header: str | None,
    ) -> Principal:
        """Resolve a trusted principal from the incoming bearer header."""
        return self._async_service.resolve_principal(authorization_header)

    def initiate_upload(
        self,
        req: InitiateUploadRequest,
        principal: Principal,
    ) -> InitiateUploadResponse:
        """Initiate an upload from a sync host."""
        return self._call_async(
            self._async_service.initiate_upload,
            req,
            principal,
        )

    def sign_parts(
        self,
        req: SignPartsRequest,
        principal: Principal,
    ) -> SignPartsResponse:
        """Presign multipart part uploads from a sync host."""
        return self._call_async(self._async_service.sign_parts, req, principal)

    def introspect_upload(
        self,
        req: UploadIntrospectionRequest,
        principal: Principal,
    ) -> UploadIntrospectionResponse:
        """Return multipart upload state from a sync host."""
        return self._call_async(
            self._async_service.introspect_upload,
            req,
            principal,
        )

    def complete_upload(
        self,
        req: CompleteUploadRequest,
        principal: Principal,
    ) -> CompleteUploadResponse:
        """Complete a multipart upload from a sync host."""
        return self._call_async(
            self._async_service.complete_upload,
            req,
            principal,
        )

    def abort_upload(
        self,
        req: AbortUploadRequest,
        principal: Principal,
    ) -> AbortUploadResponse:
        """Abort a multipart upload from a sync host."""
        return self._call_async(
            self._async_service.abort_upload,
            req,
            principal,
        )

    def presign_download(
        self,
        req: PresignDownloadRequest,
        principal: Principal,
    ) -> PresignDownloadResponse:
        """Presign an export download from a sync host."""
        return self._call_async(
            self._async_service.presign_download,
            req,
            principal,
        )

    def put_export_bytes(
        self,
        *,
        scope_id: str,
        filename: str,
        data: bytes,
        content_type: str,
    ) -> tuple[str, str]:
        """Upload export bytes directly through the sync S3 client."""
        self._async_service.ensure_enabled()
        if not data:
            raise validation_error("data is empty")
        key = self._async_service.build_export_key(
            scope_id=scope_id,
            filename=filename,
        )
        client = self._async_service.create_s3_client()
        bucket = self._async_service.bucket
        try:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise internal_error("failed to upload export object") from exc
        return bucket, key

    def download_object_bytes(
        self,
        *,
        bucket: str,
        key: str,
        max_bytes: int | None = DEFAULT_MAX_DOWNLOAD_BYTES,
    ) -> bytes:
        """Download an object while enforcing a maximum byte limit."""
        if not bucket:
            raise validation_error("bucket is required")
        if not key:
            raise validation_error("key is required")
        if max_bytes is not None and max_bytes <= 0:
            raise validation_error("max_bytes must be > 0")
        client = self._async_service.create_s3_client()
        try:
            response = client.get_object(Bucket=bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise internal_error("failed to download object") from exc
        content_length = response.get("ContentLength")
        body = response.get("Body")
        if body is None:
            raise internal_error("S3 response body is missing")

        with closing(body):
            if max_bytes is None:
                return bytes(body.read())

            if isinstance(content_length, int) and content_length > max_bytes:
                raise validation_error(
                    "object exceeds maximum download size",
                    details={
                        "content_length": content_length,
                        "max_bytes": max_bytes,
                    },
                )

            if isinstance(content_length, int):
                payload = bytes(body.read())
                if len(payload) > max_bytes:
                    raise validation_error(
                        "object exceeds maximum download size",
                        details={
                            "content_length": len(payload),
                            "max_bytes": max_bytes,
                        },
                    )
                return payload

            chunk_size = min(1024 * 1024, max_bytes + 1)
            chunks: list[bytes] = []
            total_read = 0
            while True:
                chunk = body.read(chunk_size)
                if not chunk:
                    break
                chunk_bytes = bytes(chunk)
                total_read += len(chunk_bytes)
                if total_read > max_bytes:
                    raise validation_error(
                        "object exceeds maximum download size",
                        details={
                            "content_length": total_read,
                            "max_bytes": max_bytes,
                        },
                    )
                chunks.append(chunk_bytes)
            return b"".join(chunks)


def _core_config_from_bridge(
    *,
    env_config: FileTransferEnvConfig,
    upload_policy: UploadPolicy,
) -> TransferConfig:
    return TransferConfig(
        enabled=env_config.enabled,
        bucket=env_config.bucket,
        upload_prefix=env_config.upload_prefix,
        export_prefix=env_config.export_prefix,
        tmp_prefix=env_config.tmp_prefix,
        presign_upload_ttl_seconds=env_config.presign_upload_ttl_seconds,
        presign_download_ttl_seconds=env_config.presign_download_ttl_seconds,
        multipart_threshold_bytes=(
            upload_policy.multipart_threshold_bytes
            if upload_policy.multipart_threshold_bytes is not None
            else env_config.multipart_threshold_bytes
        ),
        part_size_bytes=(
            upload_policy.part_size_bytes
            if upload_policy.part_size_bytes is not None
            else env_config.part_size_bytes
        ),
        max_concurrency=(
            upload_policy.max_concurrency
            if upload_policy.max_concurrency is not None
            else env_config.max_concurrency
        ),
        use_accelerate_endpoint=env_config.use_accelerate_endpoint,
        max_upload_bytes=upload_policy.max_upload_bytes,
    )


def coerce_file_transfer_error(exc: Exception) -> FileTransferError:
    """Convert arbitrary exceptions into bridge-level FileTransferError."""
    if isinstance(exc, FileTransferError):
        return exc
    if isinstance(exc, CoreFileTransferError):
        return FileTransferError(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )
    if isinstance(exc, ValueError):
        return validation_error(str(exc))
    return internal_error("unexpected error")
