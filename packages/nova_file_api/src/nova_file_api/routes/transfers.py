"""Transfer-domain routes for the canonical file API."""

from __future__ import annotations

from fastapi import APIRouter

from nova_file_api.dependencies import (
    PrincipalDep,
    SettingsDep,
    TransferApplicationServiceDep,
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
    SignPartsRequest,
    SignPartsResponse,
    UploadIntrospectionRequest,
    UploadIntrospectionResponse,
)
from nova_file_api.operation_ids import (
    ABORT_UPLOAD_OPERATION_ID,
    COMPLETE_UPLOAD_OPERATION_ID,
    INITIATE_UPLOAD_OPERATION_ID,
    INTROSPECT_UPLOAD_OPERATION_ID,
    PRESIGN_DOWNLOAD_OPERATION_ID,
    SIGN_UPLOAD_PARTS_OPERATION_ID,
)
from nova_file_api.routes.common import (
    COMMON_ERROR_RESPONSES,
    IDEMPOTENCY_CONFLICT_RESPONSE,
    IDEMPOTENCY_UNAVAILABLE_RESPONSE,
    IdempotencyKeyHeader,
    validated_idempotency_key,
)

transfer_router = APIRouter(
    prefix="/v1/transfers",
    tags=["transfers"],
    responses=COMMON_ERROR_RESPONSES,
)


@transfer_router.post(
    "/uploads/initiate",
    operation_id=INITIATE_UPLOAD_OPERATION_ID,
    response_model=InitiateUploadResponse,
    summary="Initiate a direct-to-S3 upload session",
    description=(
        "Resolve the effective transfer policy for the caller and return the "
        "presigned metadata needed to upload directly to S3."
    ),
    response_description=(
        "Resolved upload session metadata, policy hints, and presigned inputs."
    ),
    responses=IDEMPOTENCY_CONFLICT_RESPONSE | IDEMPOTENCY_UNAVAILABLE_RESPONSE,
)
async def initiate_upload(
    payload: InitiateUploadRequest,
    settings: SettingsDep,
    transfer_application_service: TransferApplicationServiceDep,
    principal: PrincipalDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> InitiateUploadResponse:
    """Choose upload strategy and return presigned metadata."""
    key = validated_idempotency_key(
        settings=settings,
        idempotency_key=idempotency_key,
    )
    return await transfer_application_service.initiate_upload(
        payload=payload,
        principal=principal,
        idempotency_key=key,
    )


@transfer_router.post(
    "/uploads/sign-parts",
    operation_id=SIGN_UPLOAD_PARTS_OPERATION_ID,
    response_model=SignPartsResponse,
    summary="Sign multipart upload parts",
    description=(
        "Return presigned URLs for the requested multipart upload part numbers."
    ),
    response_description="Presigned multipart part URLs and their TTL.",
)
async def sign_upload_parts(
    payload: SignPartsRequest,
    transfer_application_service: TransferApplicationServiceDep,
    principal: PrincipalDep,
) -> SignPartsResponse:
    """Return presigned multipart part URLs."""
    return await transfer_application_service.sign_parts(
        payload=payload,
        principal=principal,
    )


@transfer_router.post(
    "/uploads/introspect",
    operation_id=INTROSPECT_UPLOAD_OPERATION_ID,
    response_model=UploadIntrospectionResponse,
    summary="Inspect multipart upload state",
    description=(
        "Return the persisted multipart session state so browser or native "
        "clients can resume an interrupted upload."
    ),
    response_description=(
        "Current multipart upload state, including uploaded parts."
    ),
)
async def introspect_upload(
    payload: UploadIntrospectionRequest,
    transfer_application_service: TransferApplicationServiceDep,
    principal: PrincipalDep,
) -> UploadIntrospectionResponse:
    """Return uploaded multipart part state for resume flows."""
    return await transfer_application_service.introspect_upload(
        payload=payload,
        principal=principal,
    )


@transfer_router.post(
    "/uploads/complete",
    operation_id=COMPLETE_UPLOAD_OPERATION_ID,
    response_model=CompleteUploadResponse,
    summary="Complete a multipart upload",
    description=(
        "Finalize a multipart upload after the caller has uploaded every "
        "required part."
    ),
    response_description="Completed object metadata for the finalized upload.",
)
async def complete_upload(
    payload: CompleteUploadRequest,
    transfer_application_service: TransferApplicationServiceDep,
    principal: PrincipalDep,
) -> CompleteUploadResponse:
    """Complete multipart upload."""
    return await transfer_application_service.complete_upload(
        payload=payload,
        principal=principal,
    )


@transfer_router.post(
    "/uploads/abort",
    operation_id=ABORT_UPLOAD_OPERATION_ID,
    response_model=AbortUploadResponse,
    summary="Abort a multipart upload",
    description=(
        "Cancel an in-progress multipart upload and discard any staged parts."
    ),
    response_description=(
        "Acknowledgement that the multipart upload was aborted."
    ),
)
async def abort_upload(
    payload: AbortUploadRequest,
    transfer_application_service: TransferApplicationServiceDep,
    principal: PrincipalDep,
) -> AbortUploadResponse:
    """Abort multipart upload."""
    return await transfer_application_service.abort_upload(
        payload=payload,
        principal=principal,
    )


@transfer_router.post(
    "/downloads/presign",
    operation_id=PRESIGN_DOWNLOAD_OPERATION_ID,
    response_model=PresignDownloadResponse,
    summary="Presign a direct download",
    description=(
        "Return a time-limited download URL for an object the caller is "
        "authorized to access."
    ),
    response_description=(
        "Presigned download URL and associated object metadata."
    ),
)
async def presign_download(
    payload: PresignDownloadRequest,
    transfer_application_service: TransferApplicationServiceDep,
    principal: PrincipalDep,
) -> PresignDownloadResponse:
    """Issue presigned GET URL for caller-scoped key."""
    return await transfer_application_service.presign_download(
        payload=payload,
        principal=principal,
    )
