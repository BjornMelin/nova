"""Optional FastAPI adapter for file transfer endpoints."""
# mypy: disable-error-code="untyped-decorator"

from functools import wraps
from typing import TYPE_CHECKING, Any

import anyio
from pydantic import ValidationError

from nova_dash_bridge.config import (
    AuthPolicy,
    FileTransferEnvConfig,
    UploadPolicy,
)
from nova_dash_bridge.errors import validation_error
from nova_dash_bridge.models import (
    AbortUploadRequest,
    CompleteUploadRequest,
    ErrorBody,
    ErrorEnvelope,
    InitiateUploadRequest,
    PresignDownloadRequest,
    SignPartsRequest,
)
from nova_dash_bridge.s3_client import SupportsCreateS3Client
from nova_dash_bridge.service import (
    FileTransferService,
    coerce_file_transfer_error,
)

if TYPE_CHECKING:
    from fastapi import Request
else:  # pragma: no cover
    try:
        from fastapi import Request
    except ModuleNotFoundError:
        Request = Any  # type: ignore[misc,assignment]


def _fastapi_imports() -> tuple[type[Any], type[Any], type[Any], Any]:
    """Load FastAPI symbols only when the optional dependency is installed.

    Returns:
        tuple[type[Any], type[Any], type[Any], Any]: APIRouter,
        FastAPI, JSONResponse, and run_in_threadpool.

    Raises:
        RuntimeError: If FastAPI optional dependencies are missing.
    """
    try:
        from fastapi import APIRouter, FastAPI
        from fastapi.responses import JSONResponse
        from starlette.concurrency import run_in_threadpool
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "FastAPI integration requires optional dependency group `fastapi`"
        ) from exc
    return APIRouter, FastAPI, JSONResponse, run_in_threadpool


def _request_id(request: Request) -> str | None:
    """Read the request identifier header when present.

    Args:
        request: Incoming FastAPI request.

    Returns:
        Optional[str]: Header value from ``X-Request-Id`` or ``None``.
    """
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    value = headers.get("X-Request-Id")
    return value if isinstance(value, str) else None


def _error_payload(
    *,
    code: str,
    message: str,
    details: dict[str, Any],
    request_id: str | None,
) -> dict[str, Any]:
    """Build the canonical error envelope payload.

    Args:
        code: Stable machine-readable error code.
        message: Human-readable error message.
        details: Structured error context.
        request_id: Correlation ID from request headers.

    Returns:
        dict[str, Any]: Serialized error payload with top-level ``error``.
    """
    envelope = ErrorEnvelope(
        error=ErrorBody(
            code=code,
            message=message,
            details=details,
            request_id=request_id,
        )
    )
    return envelope.model_dump()


async def _parse_payload(request: Request, model: type[Any]) -> Any:
    """Parse and validate JSON request data into a model instance.

    Args:
        request: Incoming FastAPI request.
        model: Pydantic model type used for validation.

    Returns:
        Any: Validated model instance.

    Raises:
        FileTransferError: ``validation_error`` when JSON is invalid or
            schema validation fails.
    """
    try:
        incoming = await request.json()
    except Exception as exc:
        raise validation_error("request body must be valid JSON") from exc

    if incoming is None:
        raise validation_error("request body must not be null")

    try:
        return model.model_validate(incoming)
    except ValidationError as exc:
        raise validation_error(
            "invalid request payload",
            details={"errors": exc.errors()},
        ) from exc


def _configure_thread_limiter(*, total_tokens: int) -> None:
    """Configure AnyIO thread tokens before request handling starts."""
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = total_tokens


def create_fastapi_router(
    *,
    env_config: FileTransferEnvConfig,
    upload_policy: UploadPolicy,
    auth_policy: AuthPolicy | None = None,
    s3_client_factory: SupportsCreateS3Client | None = None,
) -> Any:
    """Create an APIRouter that serves file transfer contract endpoints.

    Args:
        env_config: Runtime environment configuration.
        upload_policy: Upload constraints and multipart configuration.
        auth_policy: Optional authorization policy.
        s3_client_factory: Optional S3 client factory override.

    Returns:
        Any: FastAPI APIRouter containing file transfer routes.
    """
    apirouter, _, json_response, run_in_threadpool = _fastapi_imports()
    router = apirouter()
    service = FileTransferService(
        env_config=env_config,
        upload_policy=upload_policy,
        auth_policy=auth_policy,
        s3_client_factory=s3_client_factory,
    )

    def handle_file_transfer_errors(handler: Any) -> Any:
        """Wrap route handlers with contract error-envelope responses."""

        @wraps(handler)
        async def wrapped(request: Request) -> Any:
            try:
                return await handler(request)
            except Exception as exc:
                err = coerce_file_transfer_error(exc)
                return json_response(
                    status_code=int(err.status_code),
                    content=_error_payload(
                        code=err.code,
                        message=err.message,
                        details=err.details,
                        request_id=_request_id(request),
                    ),
                )

        return wrapped

    @router.post("/uploads/initiate")
    @handle_file_transfer_errors
    async def initiate_upload(
        request: Request,
    ) -> Any:
        """Initiate upload and return single or multipart strategy payload."""
        payload = await _parse_payload(request, InitiateUploadRequest)
        return await run_in_threadpool(service.initiate_upload, payload)

    @router.post("/uploads/sign-parts")
    @handle_file_transfer_errors
    async def sign_parts(request: Request) -> Any:
        """Return presigned multipart part upload URLs."""
        payload = await _parse_payload(request, SignPartsRequest)
        return await run_in_threadpool(service.sign_parts, payload)

    @router.post("/uploads/complete")
    @handle_file_transfer_errors
    async def complete_upload(
        request: Request,
    ) -> Any:
        """Complete multipart upload and return final object metadata."""
        payload = await _parse_payload(request, CompleteUploadRequest)
        return await run_in_threadpool(service.complete_upload, payload)

    @router.post("/uploads/abort")
    @handle_file_transfer_errors
    async def abort_upload(request: Request) -> Any:
        """Abort an active multipart upload."""
        payload = await _parse_payload(request, AbortUploadRequest)
        return await run_in_threadpool(service.abort_upload, payload)

    @router.post("/downloads/presign")
    @handle_file_transfer_errors
    async def presign_download(
        request: Request,
    ) -> Any:
        """Return a presigned download URL for an export object."""
        payload = await _parse_payload(request, PresignDownloadRequest)
        return await run_in_threadpool(service.presign_download, payload)

    return router


def create_fastapi_app(
    *,
    env_config: FileTransferEnvConfig,
    upload_policy: UploadPolicy,
    auth_policy: AuthPolicy | None = None,
    s3_client_factory: SupportsCreateS3Client | None = None,
) -> Any:
    """Create a minimal FastAPI app with file transfer routes registered.

    Args:
        env_config: Runtime environment configuration.
        upload_policy: Upload constraints and multipart configuration.
        auth_policy: Optional authorization policy.
        s3_client_factory: Optional S3 client factory override.

    Returns:
        Any: FastAPI application instance with mounted transfer routes.
    """
    _, fastapi, _, _ = _fastapi_imports()
    app = fastapi()

    async def _startup() -> None:
        _configure_thread_limiter(total_tokens=env_config.thread_tokens)

    app.add_event_handler("startup", _startup)

    app.include_router(
        create_fastapi_router(
            env_config=env_config,
            upload_policy=upload_policy,
            auth_policy=auth_policy,
            s3_client_factory=s3_client_factory,
        ),
        prefix="/v1/transfers",
    )
    return app
