"""Pydantic API models for file transfer endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class StrictModel(BaseModel):
    """Strict base model with forbidden extra fields."""

    model_config = {"extra": "forbid"}


class InitiateUploadRequest(StrictModel):
    """Request payload for upload initiation."""

    filename: str = Field(min_length=1)
    content_type: str | None = None
    size_bytes: int = Field(gt=0)
    session_id: str = Field(
        min_length=16,
        max_length=64,
        pattern=r"^[0-9a-fA-F-]{16,64}$",
    )


class InitiateUploadResponseSingle(StrictModel):
    """Response payload for single-part presigned PUT."""

    strategy: Literal["single"] = "single"
    method: Literal["PUT"] = "PUT"
    bucket: str
    key: str
    url: str
    expires_in_seconds: int


class InitiateUploadResponseMultipart(StrictModel):
    """Response payload for multipart initiation."""

    strategy: Literal["multipart"] = "multipart"
    bucket: str
    key: str
    upload_id: str
    part_size_bytes: int
    expires_in_seconds: int


class SignPartsRequest(StrictModel):
    """Request payload for presigning multipart part uploads."""

    key: str = Field(min_length=1)
    upload_id: str = Field(min_length=1)
    part_numbers: list[int] = Field(min_length=1)
    session_id: str = Field(
        min_length=16,
        max_length=64,
        pattern=r"^[0-9a-fA-F-]{16,64}$",
    )

    @field_validator("part_numbers")
    @classmethod
    def _validate_part_numbers(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("part_numbers must be non-empty")
        if len(value) > 1000:
            raise ValueError("part_numbers must not exceed 1000")
        if len(value) != len(set(value)):
            raise ValueError("part_numbers must be unique")
        if any(number < 1 for number in value):
            raise ValueError("part_numbers must be >= 1")
        if any(number > 10_000 for number in value):
            raise ValueError("part_numbers must be <= 10000")
        return value


class SignPartsResponse(StrictModel):
    """Response payload containing signed part URLs."""

    urls: dict[str, str]
    expires_in_seconds: int


class CompletedPart(StrictModel):
    """Part completion details returned by browser client."""

    part_number: int = Field(ge=1, le=10_000)
    etag: str = Field(min_length=1)


class CompleteUploadRequest(StrictModel):
    """Request payload for completing a multipart upload."""

    key: str = Field(min_length=1)
    upload_id: str = Field(min_length=1)
    parts: list[CompletedPart] = Field(min_length=1)
    session_id: str = Field(
        min_length=16,
        max_length=64,
        pattern=r"^[0-9a-fA-F-]{16,64}$",
    )


class CompleteUploadResponse(StrictModel):
    """Response payload for multipart completion."""

    bucket: str
    key: str
    etag: str | None = None


class AbortUploadRequest(StrictModel):
    """Request payload for aborting multipart uploads."""

    key: str = Field(min_length=1)
    upload_id: str = Field(min_length=1)
    session_id: str = Field(
        min_length=16,
        max_length=64,
        pattern=r"^[0-9a-fA-F-]{16,64}$",
    )


class AbortUploadResponse(StrictModel):
    """Response payload for abort operation."""

    ok: bool = True


class PresignDownloadRequest(StrictModel):
    """Request payload for generating presigned download URL."""

    key: str = Field(min_length=1)
    session_id: str = Field(
        min_length=16,
        max_length=64,
        pattern=r"^[0-9a-fA-F-]{16,64}$",
    )
    content_disposition: Literal["inline", "attachment"] = "attachment"
    filename: str | None = None


class PresignDownloadResponse(StrictModel):
    """Response payload for presigned download URL."""

    bucket: str
    key: str
    url: str
    expires_in_seconds: int


class ErrorBody(StrictModel):
    """Error payload body."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorEnvelope(StrictModel):
    """Error envelope returned by endpoints."""

    error: ErrorBody
