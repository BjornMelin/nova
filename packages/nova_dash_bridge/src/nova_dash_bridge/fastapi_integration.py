"""Optional FastAPI adapter for file transfer endpoints."""
# mypy: disable-error-code="untyped-decorator"

from contextlib import asynccontextmanager
from functools import wraps
from json import JSONDecodeError
from typing import TYPE_CHECKING, Any, cast

from nova_file_api.public import (
    ABORT_UPLOAD_ROUTE,
    COMPLETE_UPLOAD_ROUTE,
    INTROSPECT_UPLOAD_ROUTE,
    PRESIGN_DOWNLOAD_ROUTE,
    SIGN_PARTS_ROUTE,
    TRANSFER_ROUTE_PREFIX,
    UPLOADS_INITIATE_ROUTE,
)
from nova_runtime_support.threading import current_default_thread_limiter

from nova_dash_bridge.config import (
    AuthPolicy,
    FileTransferEnvConfig,
    UploadPolicy,
)
from nova_dash_bridge.models import (
    AbortUploadRequest,
    AbortUploadResponse,
    CompleteUploadRequest,
    CompleteUploadResponse,
    ErrorBody,
    ErrorEnvelope,
    InitiateUploadRequest,
    InitiateUploadResponseMultipart,
    InitiateUploadResponseSingle,
    PresignDownloadRequest,
    PresignDownloadResponse,
    SignPartsRequest,
    SignPartsResponse,
    UploadIntrospectionRequest,
    UploadIntrospectionResponse,
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
        Request = Any


def _fastapi_imports() -> tuple[
    type[Any], type[Any], type[Any], Any, type[Any]
]:
    """Load FastAPI symbols only when the optional dependency is installed.

    Returns:
        tuple[type[Any], type[Any], type[Any], Any]: APIRouter,
        FastAPI, JSONResponse, and run_in_threadpool.

    Raises:
        RuntimeError: If FastAPI optional dependencies are missing.
    """
    try:
        from fastapi import APIRouter, FastAPI
        from fastapi.exceptions import RequestValidationError
        from fastapi.responses import JSONResponse
        from starlette.concurrency import run_in_threadpool
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "FastAPI integration requires optional dependency group `fastapi`"
        ) from exc
    return (
        APIRouter,
        FastAPI,
        JSONResponse,
        run_in_threadpool,
        RequestValidationError,
    )


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


def _configure_thread_limiter(*, total_tokens: int) -> None:
    """Configure AnyIO thread tokens before request handling starts."""
    limiter = current_default_thread_limiter()
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
    apirouter, _, json_response, run_in_threadpool, _ = _fastapi_imports()
    router = apirouter(prefix=TRANSFER_ROUTE_PREFIX)
    service = FileTransferService(
        env_config=env_config,
        upload_policy=upload_policy,
        auth_policy=auth_policy,
        s3_client_factory=s3_client_factory,
    )

    def handle_file_transfer_errors(handler: Any) -> Any:
        """Wrap route handlers with contract error-envelope responses."""

        @wraps(handler)
        async def wrapped(request: Request, *args: Any, **kwargs: Any) -> Any:
            try:
                return await handler(request, *args, **kwargs)
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

    @router.post(
        UPLOADS_INITIATE_ROUTE,
        response_model=(
            InitiateUploadResponseSingle | InitiateUploadResponseMultipart
        ),
    )
    @handle_file_transfer_errors
    async def initiate_upload(
        request: Request,
        payload: InitiateUploadRequest,
    ) -> InitiateUploadResponseSingle | InitiateUploadResponseMultipart:
        """Initiate upload and return single or multipart strategy payload."""
        return cast(
            InitiateUploadResponseSingle | InitiateUploadResponseMultipart,
            await run_in_threadpool(service.initiate_upload, payload),
        )

    @router.post(SIGN_PARTS_ROUTE, response_model=SignPartsResponse)
    @handle_file_transfer_errors
    async def sign_parts(
        request: Request,
        payload: SignPartsRequest,
    ) -> SignPartsResponse:
        """Return presigned multipart part upload URLs."""
        return cast(
            SignPartsResponse,
            await run_in_threadpool(service.sign_parts, payload),
        )

    @router.post(
        INTROSPECT_UPLOAD_ROUTE,
        response_model=UploadIntrospectionResponse,
    )
    @handle_file_transfer_errors
    async def introspect_upload(
        request: Request,
        payload: UploadIntrospectionRequest,
    ) -> UploadIntrospectionResponse:
        """Return uploaded multipart part state for resume flows."""
        return cast(
            UploadIntrospectionResponse,
            await run_in_threadpool(service.introspect_upload, payload),
        )

    @router.post(COMPLETE_UPLOAD_ROUTE, response_model=CompleteUploadResponse)
    @handle_file_transfer_errors
    async def complete_upload(
        request: Request,
        payload: CompleteUploadRequest,
    ) -> CompleteUploadResponse:
        """Complete multipart upload and return final object metadata."""
        return cast(
            CompleteUploadResponse,
            await run_in_threadpool(service.complete_upload, payload),
        )

    @router.post(ABORT_UPLOAD_ROUTE, response_model=AbortUploadResponse)
    @handle_file_transfer_errors
    async def abort_upload(
        request: Request,
        payload: AbortUploadRequest,
    ) -> AbortUploadResponse:
        """Abort an active multipart upload."""
        return cast(
            AbortUploadResponse,
            await run_in_threadpool(service.abort_upload, payload),
        )

    @router.post(
        PRESIGN_DOWNLOAD_ROUTE,
        response_model=PresignDownloadResponse,
    )
    @handle_file_transfer_errors
    async def presign_download(
        request: Request,
        payload: PresignDownloadRequest,
    ) -> PresignDownloadResponse:
        """Return a presigned download URL for an export object."""
        return cast(
            PresignDownloadResponse,
            await run_in_threadpool(service.presign_download, payload),
        )

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
    _, fastapi, json_response, _, request_validation_error = _fastapi_imports()

    @asynccontextmanager
    async def lifespan(_app: Any) -> Any:
        _configure_thread_limiter(total_tokens=env_config.thread_tokens)
        yield

    app = fastapi(lifespan=lifespan)

    @app.exception_handler(request_validation_error)
    async def handle_request_validation_error(
        request: Request,
        exc: Any,
    ) -> Any:
        return json_response(
            status_code=422,
            content=_error_payload(
                code="invalid_request",
                message="request validation failed",
                details={"errors": exc.errors()},
                request_id=_request_id(request),
            ),
        )

    @app.exception_handler(JSONDecodeError)
    async def handle_json_decode_error(request: Request, exc: Exception) -> Any:
        return json_response(
            status_code=422,
            content=_error_payload(
                code="invalid_request",
                message="request validation failed",
                details={"reason": str(exc)},
                request_id=_request_id(request),
            ),
        )

    app.include_router(
        create_fastapi_router(
            env_config=env_config,
            upload_policy=upload_policy,
            auth_policy=auth_policy,
            s3_client_factory=s3_client_factory,
        ),
    )
    return app
