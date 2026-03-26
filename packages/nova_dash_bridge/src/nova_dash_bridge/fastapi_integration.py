"""Optional FastAPI adapter for file transfer endpoints."""
# mypy: disable-error-code="untyped-decorator"

from json import JSONDecodeError
from typing import Annotated, Any, Final

from nova_file_api.public import (
    ABORT_UPLOAD_ROUTE,
    COMPLETE_UPLOAD_ROUTE,
    INTROSPECT_UPLOAD_ROUTE,
    PRESIGN_DOWNLOAD_ROUTE,
    SIGN_PARTS_ROUTE,
    TRANSFER_ROUTE_PREFIX,
    UPLOADS_INITIATE_ROUTE,
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
    UploadIntrospectionRequest,
    UploadIntrospectionResponse,
)
from nova_runtime_support import (
    CanonicalErrorSpec,
    RequestContextFastAPI,
    canonical_error_spec_from_error,
    register_fastapi_exception_handlers,
)

from nova_dash_bridge.config import (
    AuthPolicy,
    FileTransferEnvConfig,
    UploadPolicy,
)
from nova_dash_bridge.errors import FileTransferError, unauthorized_error
from nova_dash_bridge.s3_client import (
    SupportsCreateAsyncS3Client,
    SupportsCreateS3Client,
)
from nova_dash_bridge.service import (
    AsyncFileTransferService,
    coerce_file_transfer_error,
)

INITIATE_UPLOAD_OPERATION_ID: Final = "initiate_upload"
SIGN_UPLOAD_PARTS_OPERATION_ID: Final = "sign_upload_parts"
INTROSPECT_UPLOAD_OPERATION_ID: Final = "introspect_upload"
COMPLETE_UPLOAD_OPERATION_ID: Final = "complete_upload"
ABORT_UPLOAD_OPERATION_ID: Final = "abort_upload"
PRESIGN_DOWNLOAD_OPERATION_ID: Final = "presign_download"


def _fastapi_imports() -> tuple[type[Any], type[Any]]:
    """Load FastAPI symbols only when the optional dependency is installed."""
    try:
        from fastapi import APIRouter, FastAPI
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "FastAPI integration requires optional dependency group `fastapi`"
        ) from exc
    return (APIRouter, FastAPI)


def create_fastapi_router(
    *,
    env_config: FileTransferEnvConfig,
    upload_policy: UploadPolicy,
    auth_policy: AuthPolicy,
    s3_client_factory: SupportsCreateS3Client | None = None,
    async_s3_client_factory: SupportsCreateAsyncS3Client | None = None,
) -> Any:
    """Create route-only FastAPI composition for file transfer endpoints."""
    if auth_policy.async_principal_resolver is None:
        raise TypeError(
            "FastAPI integration requires auth_policy.async_principal_resolver"
        )
    sync_factory = s3_client_factory or None
    if (
        async_s3_client_factory is None
        and sync_factory is not None
        and not callable(getattr(sync_factory, "create_async", None))
    ):
        raise TypeError(
            "FastAPI integration requires async_s3_client_factory or "
            "s3_client_factory with create_async()"
        )
    apirouter, _ = _fastapi_imports()
    router = apirouter(prefix=TRANSFER_ROUTE_PREFIX, tags=["transfers"])
    service = AsyncFileTransferService(
        env_config=env_config,
        upload_policy=upload_policy,
        auth_policy=auth_policy,
        s3_client_factory=s3_client_factory,
        async_s3_client_factory=async_s3_client_factory,
    )
    from fastapi import Depends, Security
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    bearer_auth = HTTPBearer(
        auto_error=False,
        scheme_name="bearerAuth",
        bearerFormat="JWT",
    )

    async def _resolve_principal(
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
        return await service.resolve_principal_async(
            authorization_header,
        )

    @router.post(
        UPLOADS_INITIATE_ROUTE,
        operation_id=INITIATE_UPLOAD_OPERATION_ID,
        response_model=InitiateUploadResponse,
    )
    async def initiate_upload(
        payload: InitiateUploadRequest,
        principal: Annotated[Principal, Depends(_resolve_principal)],
    ) -> InitiateUploadResponse:
        return await service.initiate_upload(payload, principal=principal)

    @router.post(
        SIGN_PARTS_ROUTE,
        operation_id=SIGN_UPLOAD_PARTS_OPERATION_ID,
        response_model=SignPartsResponse,
    )
    async def sign_parts(
        payload: SignPartsRequest,
        principal: Annotated[Principal, Depends(_resolve_principal)],
    ) -> SignPartsResponse:
        return await service.sign_parts(payload, principal=principal)

    @router.post(
        INTROSPECT_UPLOAD_ROUTE,
        operation_id=INTROSPECT_UPLOAD_OPERATION_ID,
        response_model=UploadIntrospectionResponse,
    )
    async def introspect_upload(
        payload: UploadIntrospectionRequest,
        principal: Annotated[Principal, Depends(_resolve_principal)],
    ) -> UploadIntrospectionResponse:
        return await service.introspect_upload(payload, principal=principal)

    @router.post(
        COMPLETE_UPLOAD_ROUTE,
        operation_id=COMPLETE_UPLOAD_OPERATION_ID,
        response_model=CompleteUploadResponse,
    )
    async def complete_upload(
        payload: CompleteUploadRequest,
        principal: Annotated[Principal, Depends(_resolve_principal)],
    ) -> CompleteUploadResponse:
        return await service.complete_upload(payload, principal=principal)

    @router.post(
        ABORT_UPLOAD_ROUTE,
        operation_id=ABORT_UPLOAD_OPERATION_ID,
        response_model=AbortUploadResponse,
    )
    async def abort_upload(
        payload: AbortUploadRequest,
        principal: Annotated[Principal, Depends(_resolve_principal)],
    ) -> AbortUploadResponse:
        return await service.abort_upload(payload, principal=principal)

    @router.post(
        PRESIGN_DOWNLOAD_ROUTE,
        operation_id=PRESIGN_DOWNLOAD_OPERATION_ID,
        response_model=PresignDownloadResponse,
    )
    async def presign_download(
        payload: PresignDownloadRequest,
        principal: Annotated[Principal, Depends(_resolve_principal)],
    ) -> PresignDownloadResponse:
        return await service.presign_download(payload, principal=principal)

    return router


def create_fastapi_app(
    *,
    env_config: FileTransferEnvConfig,
    upload_policy: UploadPolicy,
    auth_policy: AuthPolicy,
    s3_client_factory: SupportsCreateS3Client | None = None,
    async_s3_client_factory: SupportsCreateAsyncS3Client | None = None,
) -> Any:
    """Create the canonical bridge FastAPI app with shared transport wiring."""
    _fastapi_imports()

    app = RequestContextFastAPI()
    register_fastapi_exception_handlers(
        app,
        domain_error_type=FileTransferError,
        adapt_domain_error=canonical_error_spec_from_error,
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
            async_s3_client_factory=async_s3_client_factory,
        ),
    )
    return app


def _bridge_unhandled_error_spec(exc: Exception) -> CanonicalErrorSpec:
    """Coerce unexpected bridge exceptions into canonical transport errors."""
    return canonical_error_spec_from_error(coerce_file_transfer_error(exc))


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
