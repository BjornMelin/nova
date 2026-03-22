"""Optional FastAPI adapter for file transfer endpoints."""
# mypy: disable-error-code="untyped-decorator"

from contextlib import asynccontextmanager
from json import JSONDecodeError
from typing import Annotated, Any, Final, cast

from nova_file_api.public import (
    ABORT_UPLOAD_ROUTE,
    COMPLETE_UPLOAD_ROUTE,
    INTROSPECT_UPLOAD_ROUTE,
    PRESIGN_DOWNLOAD_ROUTE,
    SIGN_PARTS_ROUTE,
    TRANSFER_ROUTE_PREFIX,
    UPLOADS_INITIATE_ROUTE,
    Principal,
)
from nova_runtime_support import (
    CanonicalErrorSpec,
    RequestContextFastAPI,
    register_fastapi_exception_handlers,
)
from nova_runtime_support.threading import current_default_thread_limiter

from nova_dash_bridge.config import (
    AuthPolicy,
    FileTransferEnvConfig,
    UploadPolicy,
)
from nova_dash_bridge.errors import FileTransferError, unauthorized_error
from nova_dash_bridge.models import (
    AbortUploadRequest,
    AbortUploadResponse,
    CompleteUploadRequest,
    CompleteUploadResponse,
    InitiateUploadRequest,
    InitiateUploadResponse,
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

INITIATE_UPLOAD_OPERATION_ID: Final = "initiate_upload"
SIGN_UPLOAD_PARTS_OPERATION_ID: Final = "sign_upload_parts"
INTROSPECT_UPLOAD_OPERATION_ID: Final = "introspect_upload"
COMPLETE_UPLOAD_OPERATION_ID: Final = "complete_upload"
ABORT_UPLOAD_OPERATION_ID: Final = "abort_upload"
PRESIGN_DOWNLOAD_OPERATION_ID: Final = "presign_download"


def _fastapi_imports() -> tuple[type[Any], type[Any], Any]:
    """Load FastAPI symbols only when the optional dependency is installed.

    Returns:
        tuple[type[Any], type[Any], Any]: APIRouter, FastAPI,
        and run_in_threadpool.

    Raises:
        RuntimeError: If FastAPI optional dependencies are missing.
    """
    try:
        from fastapi import APIRouter, FastAPI
        from starlette.concurrency import run_in_threadpool
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "FastAPI integration requires optional dependency group `fastapi`"
        ) from exc
    return (APIRouter, FastAPI, run_in_threadpool)


def _error_headers(err: FileTransferError) -> dict[str, str]:
    """Return response headers for canonical bridge file-transfer errors."""
    headers = dict(getattr(err, "headers", {}))
    if int(err.status_code) == 401 and "WWW-Authenticate" not in headers:
        headers["WWW-Authenticate"] = (
            'Bearer error="invalid_token", '
            'error_description="missing bearer token"'
        )
    return headers


def _configure_thread_limiter(*, total_tokens: int) -> None:
    """Configure AnyIO thread tokens before request handling starts."""
    limiter = current_default_thread_limiter()
    limiter.total_tokens = total_tokens


def create_fastapi_router(
    *,
    env_config: FileTransferEnvConfig,
    upload_policy: UploadPolicy,
    auth_policy: AuthPolicy,
    s3_client_factory: SupportsCreateS3Client | None = None,
) -> Any:
    """Create route-only FastAPI composition for file transfer endpoints.

    Args:
        env_config: Runtime environment configuration.
        upload_policy: Upload constraints and multipart configuration.
        auth_policy: Authorization policy.
        s3_client_factory: Optional S3 client factory override.

    Returns:
        Any: FastAPI APIRouter containing file transfer routes.

    Notes:
        This router does not install Nova's canonical request-context or error
        handling stack. Standalone FastAPI hosts must wrap it with the shared
        runtime-support transport helpers or use ``create_fastapi_app()``.
    """
    apirouter, _, run_in_threadpool = _fastapi_imports()
    router = apirouter(prefix=TRANSFER_ROUTE_PREFIX, tags=["transfers"])
    service = FileTransferService(
        env_config=env_config,
        upload_policy=upload_policy,
        auth_policy=auth_policy,
        s3_client_factory=s3_client_factory,
    )
    from fastapi import Depends, Security
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    bearer_auth = HTTPBearer(
        auto_error=False,
        scheme_name="bearerAuth",
        bearerFormat="JWT",
    )

    def _resolve_principal(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Security(bearer_auth),
        ],
    ) -> Principal:
        if credentials is None or not credentials.credentials.strip():
            raise unauthorized_error("missing bearer token")
        authorization_header = (
            f"{credentials.scheme} {credentials.credentials.strip()}"
        )
        return service.resolve_principal(authorization_header)

    PrincipalDep = Annotated[Principal, Depends(_resolve_principal)]

    @router.post(
        UPLOADS_INITIATE_ROUTE,
        operation_id=INITIATE_UPLOAD_OPERATION_ID,
        response_model=InitiateUploadResponse,
    )
    async def initiate_upload(
        payload: InitiateUploadRequest,
        principal: PrincipalDep,
    ) -> InitiateUploadResponse:
        """Initiate upload and return single or multipart strategy payload."""
        return cast(
            InitiateUploadResponse,
            await run_in_threadpool(
                service.initiate_upload,
                payload,
                principal=principal,
            ),
        )

    @router.post(
        SIGN_PARTS_ROUTE,
        operation_id=SIGN_UPLOAD_PARTS_OPERATION_ID,
        response_model=SignPartsResponse,
    )
    async def sign_parts(
        payload: SignPartsRequest,
        principal: PrincipalDep,
    ) -> SignPartsResponse:
        """Return presigned multipart part upload URLs."""
        return cast(
            SignPartsResponse,
            await run_in_threadpool(
                service.sign_parts,
                payload,
                principal=principal,
            ),
        )

    @router.post(
        INTROSPECT_UPLOAD_ROUTE,
        operation_id=INTROSPECT_UPLOAD_OPERATION_ID,
        response_model=UploadIntrospectionResponse,
    )
    async def introspect_upload(
        payload: UploadIntrospectionRequest,
        principal: PrincipalDep,
    ) -> UploadIntrospectionResponse:
        """Return uploaded multipart part state for resume flows."""
        return cast(
            UploadIntrospectionResponse,
            await run_in_threadpool(
                service.introspect_upload,
                payload,
                principal=principal,
            ),
        )

    @router.post(
        COMPLETE_UPLOAD_ROUTE,
        operation_id=COMPLETE_UPLOAD_OPERATION_ID,
        response_model=CompleteUploadResponse,
    )
    async def complete_upload(
        payload: CompleteUploadRequest,
        principal: PrincipalDep,
    ) -> CompleteUploadResponse:
        """Complete multipart upload and return final object metadata."""
        return cast(
            CompleteUploadResponse,
            await run_in_threadpool(
                service.complete_upload,
                payload,
                principal=principal,
            ),
        )

    @router.post(
        ABORT_UPLOAD_ROUTE,
        operation_id=ABORT_UPLOAD_OPERATION_ID,
        response_model=AbortUploadResponse,
    )
    async def abort_upload(
        payload: AbortUploadRequest,
        principal: PrincipalDep,
    ) -> AbortUploadResponse:
        """Abort an active multipart upload."""
        return cast(
            AbortUploadResponse,
            await run_in_threadpool(
                service.abort_upload,
                payload,
                principal=principal,
            ),
        )

    @router.post(
        PRESIGN_DOWNLOAD_ROUTE,
        operation_id=PRESIGN_DOWNLOAD_OPERATION_ID,
        response_model=PresignDownloadResponse,
    )
    async def presign_download(
        payload: PresignDownloadRequest,
        principal: PrincipalDep,
    ) -> PresignDownloadResponse:
        """Return a presigned download URL for an export object."""
        return cast(
            PresignDownloadResponse,
            await run_in_threadpool(
                service.presign_download,
                payload,
                principal=principal,
            ),
        )

    return router


def create_fastapi_app(
    *,
    env_config: FileTransferEnvConfig,
    upload_policy: UploadPolicy,
    auth_policy: AuthPolicy,
    s3_client_factory: SupportsCreateS3Client | None = None,
) -> Any:
    """Create the canonical bridge FastAPI app with shared transport wiring.

    Args:
        env_config: Runtime environment configuration.
        upload_policy: Upload constraints and multipart configuration.
        auth_policy: Authorization policy.
        s3_client_factory: Optional S3 client factory override.

    Returns:
        Any: FastAPI application instance with mounted transfer routes.
    """
    _fastapi_imports()

    @asynccontextmanager
    async def lifespan(_app: Any) -> Any:
        previous_thread_tokens = int(
            current_default_thread_limiter().total_tokens
        )
        _configure_thread_limiter(total_tokens=env_config.thread_tokens)
        try:
            yield
        finally:
            _configure_thread_limiter(total_tokens=previous_thread_tokens)

    app = RequestContextFastAPI(lifespan=lifespan)
    register_fastapi_exception_handlers(
        app,
        domain_error_type=FileTransferError,
        adapt_domain_error=_bridge_error_spec,
        validation_error_details=_validation_error_details,
        adapt_unhandled_error=_bridge_unhandled_error_spec,
        extra_exception_adapters={JSONDecodeError: _json_decode_error_spec},
        logger_name="nova_dash_bridge.fastapi",
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


def _bridge_error_spec(exc: FileTransferError) -> CanonicalErrorSpec:
    """Adapt a bridge file-transfer error into the shared transport shape."""
    return CanonicalErrorSpec(
        status_code=int(exc.status_code),
        code=exc.code,
        message=exc.message,
        details=exc.details,
        headers=_error_headers(exc),
    )


def _bridge_unhandled_error_spec(exc: Exception) -> CanonicalErrorSpec:
    """Coerce unexpected bridge exceptions into canonical transport errors."""
    return _bridge_error_spec(coerce_file_transfer_error(exc))


def _validation_error_details(exc: Any) -> dict[str, object]:
    """Return public validation details for FastAPI request errors."""
    return {"errors": exc.errors()}


def _json_decode_error_spec(exc: Exception) -> CanonicalErrorSpec:
    """Return the canonical malformed-JSON transport error."""
    return CanonicalErrorSpec(
        status_code=422,
        code="invalid_request",
        message="request validation failed",
        details={"reason": str(exc)},
    )
