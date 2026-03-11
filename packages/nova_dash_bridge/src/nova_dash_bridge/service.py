"""Bridge service delegating core transfer operations to nova_file_api."""

from __future__ import annotations

import asyncio
import logging
import math
import re
import threading
from collections.abc import Callable, Coroutine
from contextlib import closing, suppress
from pathlib import Path
from typing import Any, TypeVar, cast
from urllib.parse import quote_from_bytes
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from nova_file_api.config import Settings as CoreSettings
from nova_file_api.errors import FileTransferError as CoreFileTransferError
from nova_file_api.models import (
    AbortUploadRequest as CoreAbortUploadRequest,
)
from nova_file_api.models import (
    CompletedPart as CoreCompletedPart,
)
from nova_file_api.models import (
    CompleteUploadRequest as CoreCompleteUploadRequest,
)
from nova_file_api.models import (
    InitiateUploadRequest as CoreInitiateUploadRequest,
)
from nova_file_api.models import (
    PresignDownloadRequest as CorePresignDownloadRequest,
)
from nova_file_api.models import (
    Principal,
    UploadStrategy,
)
from nova_file_api.models import (
    SignPartsRequest as CoreSignPartsRequest,
)
from nova_file_api.models import (
    UploadIntrospectionRequest as CoreUploadIntrospectionRequest,
)
from nova_file_api.models import (
    UploadIntrospectionResponse as CoreUploadIntrospectionResponse,
)
from nova_file_api.transfer import TransferService

from nova_dash_bridge.config import (
    AuthPolicy,
    FileTransferEnvConfig,
    UploadPolicy,
)
from nova_dash_bridge.errors import (
    FileTransferError,
    conflict_error,
    internal_error,
    validation_error,
)
from nova_dash_bridge.models import (
    AbortUploadRequest,
    AbortUploadResponse,
    CompleteUploadRequest,
    CompleteUploadResponse,
    InitiateUploadRequest,
    InitiateUploadResponseMultipart,
    InitiateUploadResponseSingle,
    PresignDownloadRequest,
    PresignDownloadResponse,
    SignPartsRequest,
    SignPartsResponse,
    UploadedPart,
    UploadIntrospectionRequest,
    UploadIntrospectionResponse,
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
        """Store the bridge-managed sync S3 client."""
        self._client = client

    async def generate_presigned_url(self, **kwargs: Any) -> str:
        """Generate a presigned URL using the sync boto3 client."""
        return str(
            await asyncio.to_thread(
                self._client.generate_presigned_url,
                **kwargs,
            )
        )

    async def create_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        """Create a multipart upload with the sync boto3 client."""
        return cast(
            dict[str, Any],
            await asyncio.to_thread(
                self._client.create_multipart_upload,
                **kwargs,
            ),
        )

    async def complete_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        """Complete multipart upload with the sync boto3 client."""
        return cast(
            dict[str, Any],
            await asyncio.to_thread(
                self._client.complete_multipart_upload,
                **kwargs,
            ),
        )

    async def abort_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        """Abort multipart upload with the sync boto3 client."""
        return cast(
            dict[str, Any],
            await asyncio.to_thread(
                self._client.abort_multipart_upload,
                **kwargs,
            ),
        )

    async def head_object(self, **kwargs: Any) -> dict[str, Any]:
        """Fetch object metadata using the sync boto3 client."""
        return cast(
            dict[str, Any],
            await asyncio.to_thread(self._client.head_object, **kwargs),
        )

    async def list_parts(self, **kwargs: Any) -> dict[str, Any]:
        """List uploaded multipart parts using the sync boto3 client."""
        return cast(
            dict[str, Any],
            await asyncio.to_thread(self._client.list_parts, **kwargs),
        )

    async def copy_object(self, **kwargs: Any) -> dict[str, Any]:
        """Copy an object using the sync boto3 client."""
        return cast(
            dict[str, Any],
            await asyncio.to_thread(self._client.copy_object, **kwargs),
        )

    async def upload_part_copy(self, **kwargs: Any) -> dict[str, Any]:
        """Copy a multipart range using the sync boto3 client."""
        return cast(
            dict[str, Any],
            await asyncio.to_thread(self._client.upload_part_copy, **kwargs),
        )


class FileTransferService:
    """Bridge-level service with thin delegation to core transfer runtime."""

    DEFAULT_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024

    def __init__(
        self,
        *,
        env_config: FileTransferEnvConfig,
        upload_policy: UploadPolicy,
        auth_policy: AuthPolicy | None = None,
        s3_client_factory: SupportsCreateS3Client | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize bridge service dependencies."""
        self._env = env_config
        self._policy = upload_policy
        self._auth = auth_policy or AuthPolicy()
        self._factory = s3_client_factory or S3ClientFactory()
        self._logger = logger or logging.getLogger(__name__)
        self._core_settings = _core_settings_from_bridge(
            env_config=env_config,
            upload_policy=upload_policy,
        )
        self._core_service: TransferService | None = None
        self._core_service_lock = threading.Lock()

    @property
    def part_size_bytes(self) -> int:
        """Return configured multipart part size."""
        return (
            self._policy.part_size_bytes
            if self._policy.part_size_bytes is not None
            else self._env.part_size_bytes
        )

    @property
    def multipart_threshold_bytes(self) -> int:
        """Return configured multipart threshold."""
        return (
            self._policy.multipart_threshold_bytes
            if self._policy.multipart_threshold_bytes is not None
            else self._env.multipart_threshold_bytes
        )

    def ensure_enabled(self) -> None:
        """Validate file transfer is enabled and minimally configured."""
        if not self._env.enabled:
            raise conflict_error("file transfer is not enabled")
        if not self._env.bucket:
            raise internal_error("FILE_TRANSFER_BUCKET is not configured")

    def _client(self) -> S3Client:
        """Return an S3 client from bridge factory configuration."""
        return self._factory.create(self._env)

    def _build_core_service(self) -> TransferService:
        """Build and cache a core transfer service for repeated bridge calls."""
        service = self._core_service
        if service is not None:
            return service
        with self._core_service_lock:
            service = self._core_service
            if service is None:
                service = TransferService(
                    settings=self._core_settings,
                    s3_client=_AsyncS3ClientAdapter(client=self._client()),
                )
                self._core_service = service
        return service

    @staticmethod
    def _run_async(factory: Callable[[], Coroutine[Any, Any, _T]]) -> _T:
        """Execute one async operation from the synchronous bridge layer."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(factory())
            finally:
                with suppress(Exception):
                    loop.run_until_complete(loop.shutdown_asyncgens())
                with suppress(Exception):
                    loop.run_until_complete(loop.shutdown_default_executor())
                loop.close()
        raise RuntimeError(
            "FileTransferService sync methods cannot run inside an active "
            "event loop"
        )

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Return a safe filename for key generation and download headers."""
        name = Path(filename).name
        stem = Path(name).stem.strip()
        ext = Path(name).suffix.lower()
        safe_stem = _INVALID_FILENAME_RE.sub("_", stem).strip("._")
        if not safe_stem:
            safe_stem = "upload"
        return f"{safe_stem}{ext}"

    @staticmethod
    def _coerce_prefix(prefix: str) -> str:
        """Normalize key prefixes and reject empty values."""
        raw = prefix.strip()
        if not raw:
            raise FileTransferError(
                code="validation_error",
                message=f"prefix must be non-empty: {prefix!r}",
                details={"prefix": prefix},
            )
        return raw if raw.endswith("/") else f"{raw}/"

    def resolve_scope_id(
        self,
        session_id: str | None,
    ) -> str:
        """Resolve and validate scope id used for object boundaries."""
        try:
            return self._auth.resolve_scope_id(session_id)
        except ValueError as exc:
            raise validation_error(str(exc)) from exc

    def _principal(self, *, session_id: str | None) -> Principal:
        """Build a core principal from bridge auth/session policy."""
        scope_id = self.resolve_scope_id(session_id)
        return Principal(subject=scope_id, scope_id=scope_id)

    def build_upload_key(self, *, scope_id: str, filename: str) -> str:
        """Build a server-generated upload key."""
        safe_name = self.sanitize_filename(filename)
        prefix = self._coerce_prefix(self._env.upload_prefix)
        return f"{prefix}{scope_id}/{uuid4()}/{safe_name}"

    def build_export_key(self, *, scope_id: str, filename: str) -> str:
        """Build a server-generated export key."""
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
        """Validate key stays under allowed prefix and scope."""
        prefix = self._coerce_prefix(allowed_prefix)
        if not key.startswith(prefix):
            raise validation_error("key is outside the allowed prefix")
        scoped = f"{prefix}{scope_id}/"
        if not key.startswith(scoped):
            raise validation_error("key is outside the session scope")

    def multipart_part_count(self, *, size_bytes: int) -> int:
        """Return multipart part count for configured part size."""
        if size_bytes <= 0:
            return 1
        return math.ceil(size_bytes / float(self.part_size_bytes))

    def select_upload_strategy(self, *, size_bytes: int) -> str:
        """Return upload strategy based on size policy."""
        return (
            "multipart"
            if size_bytes >= self.multipart_threshold_bytes
            else "single"
        )

    def validate_upload_request(self, req: InitiateUploadRequest) -> None:
        """Validate upload request against bridge policy constraints."""
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

    def initiate_upload(
        self,
        req: InitiateUploadRequest,
    ) -> InitiateUploadResponseSingle | InitiateUploadResponseMultipart:
        """Initiate upload and return bridge response contract."""
        self.ensure_enabled()
        self.validate_upload_request(req)
        principal = self._principal(session_id=req.session_id)
        core_response = self._run_async(
            lambda: self._build_core_service().initiate_upload(
                CoreInitiateUploadRequest(
                    filename=req.filename,
                    content_type=req.content_type,
                    size_bytes=req.size_bytes,
                    session_id=None,
                ),
                principal,
            )
        )
        if core_response.strategy == UploadStrategy.SINGLE:
            if core_response.url is None:
                raise internal_error("missing presigned upload URL")
            return InitiateUploadResponseSingle(
                bucket=core_response.bucket,
                key=core_response.key,
                url=core_response.url,
                expires_in_seconds=core_response.expires_in_seconds,
            )

        if core_response.upload_id is None:
            raise internal_error("missing multipart upload id")
        if core_response.part_size_bytes is None:
            raise internal_error("missing multipart part size")
        return InitiateUploadResponseMultipart(
            bucket=core_response.bucket,
            key=core_response.key,
            upload_id=core_response.upload_id,
            part_size_bytes=core_response.part_size_bytes,
            expires_in_seconds=core_response.expires_in_seconds,
        )

    def sign_parts(self, req: SignPartsRequest) -> SignPartsResponse:
        """Presign multipart upload part URLs."""
        self.ensure_enabled()
        principal = self._principal(session_id=req.session_id)
        core_response = self._run_async(
            lambda: self._build_core_service().sign_parts(
                CoreSignPartsRequest(
                    key=req.key,
                    upload_id=req.upload_id,
                    part_numbers=req.part_numbers,
                    session_id=None,
                ),
                principal,
            )
        )
        return SignPartsResponse(
            urls={
                str(part_number): url
                for part_number, url in core_response.urls.items()
            },
            expires_in_seconds=core_response.expires_in_seconds,
        )

    def introspect_upload(
        self,
        req: UploadIntrospectionRequest,
    ) -> UploadIntrospectionResponse:
        """Inspect uploaded multipart parts for resume flows."""
        self.ensure_enabled()
        principal = self._principal(session_id=req.session_id)
        core_response = self._run_async(
            lambda: self._build_core_service().introspect_upload(
                CoreUploadIntrospectionRequest(
                    key=req.key,
                    upload_id=req.upload_id,
                    session_id=None,
                ),
                principal,
            )
        )
        return _bridge_upload_introspection_response(core_response)

    def complete_upload(
        self,
        req: CompleteUploadRequest,
    ) -> CompleteUploadResponse:
        """Complete multipart upload and return bridge response."""
        self.ensure_enabled()
        principal = self._principal(session_id=req.session_id)
        core_parts = [
            CoreCompletedPart(
                part_number=part.part_number,
                etag=part.etag,
            )
            for part in req.parts
        ]
        core_response = self._run_async(
            lambda: self._build_core_service().complete_upload(
                CoreCompleteUploadRequest(
                    key=req.key,
                    upload_id=req.upload_id,
                    parts=core_parts,
                    session_id=None,
                ),
                principal,
            )
        )
        return CompleteUploadResponse(
            bucket=core_response.bucket,
            key=core_response.key,
            etag=core_response.etag,
        )

    def abort_upload(self, req: AbortUploadRequest) -> AbortUploadResponse:
        """Abort multipart upload and return bridge response."""
        self.ensure_enabled()
        principal = self._principal(session_id=req.session_id)
        self._run_async(
            lambda: self._build_core_service().abort_upload(
                CoreAbortUploadRequest(
                    key=req.key,
                    upload_id=req.upload_id,
                    session_id=None,
                ),
                principal,
            )
        )
        return AbortUploadResponse()

    @classmethod
    def _build_content_disposition(
        cls,
        *,
        content_disposition: str,
        filename: str,
    ) -> str:
        """Build safe content-disposition value for downloads."""
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

    def presign_download(
        self,
        req: PresignDownloadRequest,
    ) -> PresignDownloadResponse:
        """Generate presigned GET URL for export objects."""
        self.ensure_enabled()
        scope_id = self.resolve_scope_id(req.session_id)
        self.ensure_key_scoped(
            key=req.key,
            scope_id=scope_id,
            allowed_prefix=self._env.export_prefix,
        )
        disposition: str = req.content_disposition
        if req.filename:
            disposition = self._build_content_disposition(
                content_disposition=req.content_disposition,
                filename=req.filename,
            )
        core_response = self._run_async(
            lambda: self._build_core_service().presign_download(
                CorePresignDownloadRequest(
                    key=req.key,
                    session_id=None,
                    content_disposition=disposition,
                    filename=req.filename,
                    content_type=None,
                ),
                self._principal(session_id=scope_id),
            )
        )
        return PresignDownloadResponse(
            bucket=core_response.bucket,
            key=core_response.key,
            url=core_response.url,
            expires_in_seconds=core_response.expires_in_seconds,
        )

    def put_export_bytes(
        self,
        *,
        scope_id: str,
        filename: str,
        data: bytes,
        content_type: str,
    ) -> tuple[str, str]:
        """Upload generated export bytes and return `(bucket, key)`."""
        self.ensure_enabled()
        if not data:
            raise validation_error("data is empty")
        key = self.build_export_key(scope_id=scope_id, filename=filename)
        client = self._client()
        try:
            client.put_object(
                Bucket=self._env.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise internal_error("failed to upload export object") from exc
        return self._env.bucket, key

    def download_object_bytes(
        self,
        *,
        bucket: str,
        key: str,
        max_bytes: int | None = DEFAULT_MAX_DOWNLOAD_BYTES,
    ) -> bytes:
        """Download object bytes for sync processing paths."""
        if not bucket:
            raise validation_error("bucket is required")
        if not key:
            raise validation_error("key is required")
        if max_bytes is not None and max_bytes <= 0:
            raise validation_error("max_bytes must be > 0")
        client = self._client()
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


def _core_settings_from_bridge(
    *,
    env_config: FileTransferEnvConfig,
    upload_policy: UploadPolicy,
) -> CoreSettings:
    """Build core runtime settings from bridge env + policy values."""
    settings = CoreSettings()
    settings.file_transfer_enabled = env_config.enabled
    settings.file_transfer_bucket = env_config.bucket
    settings.file_transfer_upload_prefix = env_config.upload_prefix
    settings.file_transfer_export_prefix = env_config.export_prefix
    settings.file_transfer_tmp_prefix = env_config.tmp_prefix
    settings.file_transfer_presign_upload_ttl_seconds = (
        env_config.presign_upload_ttl_seconds
    )
    settings.file_transfer_presign_download_ttl_seconds = (
        env_config.presign_download_ttl_seconds
    )
    settings.file_transfer_multipart_threshold_bytes = (
        upload_policy.multipart_threshold_bytes
        if upload_policy.multipart_threshold_bytes is not None
        else env_config.multipart_threshold_bytes
    )
    settings.file_transfer_part_size_bytes = (
        upload_policy.part_size_bytes
        if upload_policy.part_size_bytes is not None
        else env_config.part_size_bytes
    )
    settings.file_transfer_max_concurrency = (
        upload_policy.max_concurrency
        if upload_policy.max_concurrency is not None
        else env_config.max_concurrency
    )
    settings.file_transfer_use_accelerate_endpoint = (
        env_config.use_accelerate_endpoint
    )
    settings.max_upload_bytes = upload_policy.max_upload_bytes
    return settings


def _bridge_upload_introspection_response(
    response: CoreUploadIntrospectionResponse,
) -> UploadIntrospectionResponse:
    """Convert core multipart introspection payload to bridge model."""
    return UploadIntrospectionResponse(
        bucket=response.bucket,
        key=response.key,
        upload_id=response.upload_id,
        part_size_bytes=response.part_size_bytes,
        parts=[
            UploadedPart(part_number=part.part_number, etag=part.etag)
            for part in response.parts
        ],
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
