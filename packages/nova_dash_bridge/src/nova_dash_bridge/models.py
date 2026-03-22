"""Bridge-facing transfer models re-exported from the canonical public API."""

import nova_file_api.public as _public

AbortUploadRequest = _public.AbortUploadRequest
AbortUploadResponse = _public.AbortUploadResponse
CompleteUploadRequest = _public.CompleteUploadRequest
CompleteUploadResponse = _public.CompleteUploadResponse
CompletedPart = _public.CompletedPart
ErrorEnvelope = _public.ErrorEnvelope
InitiateUploadRequest = _public.InitiateUploadRequest
InitiateUploadResponse = _public.InitiateUploadResponse
PresignDownloadRequest = _public.PresignDownloadRequest
PresignDownloadResponse = _public.PresignDownloadResponse
SignPartsRequest = _public.SignPartsRequest
SignPartsResponse = _public.SignPartsResponse
UploadedPart = _public.UploadedPart
UploadIntrospectionRequest = _public.UploadIntrospectionRequest
UploadIntrospectionResponse = _public.UploadIntrospectionResponse

__all__ = sorted(
    [
        "AbortUploadRequest",
        "AbortUploadResponse",
        "CompleteUploadRequest",
        "CompleteUploadResponse",
        "CompletedPart",
        "ErrorEnvelope",
        "InitiateUploadRequest",
        "InitiateUploadResponse",
        "PresignDownloadRequest",
        "PresignDownloadResponse",
        "SignPartsRequest",
        "SignPartsResponse",
        "UploadedPart",
        "UploadIntrospectionRequest",
        "UploadIntrospectionResponse",
    ]
)
