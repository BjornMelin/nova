"""Pydantic and domain models for the transfer API."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from nova_runtime_support.export_models import (
    ExportOutput,
    ExportRecord,
    ExportStatus,
)


class UploadStrategy(StrEnum):
    """Upload strategy options returned by initiate endpoint."""

    SINGLE = "single"
    MULTIPART = "multipart"


class ActivityStoreBackend(StrEnum):
    """Storage backends for activity rollups."""

    MEMORY = "memory"
    DYNAMODB = "dynamodb"


class Principal(BaseModel):
    """Authorized caller identity used for scope enforcement."""

    model_config = ConfigDict(extra="forbid")

    subject: str
    scope_id: str
    tenant_id: str | None = None
    scopes: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()


class InitiateUploadRequest(BaseModel):
    """Initiate-upload request model."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=512)
    content_type: str | None = Field(default=None, max_length=256)
    size_bytes: int = Field(gt=0)


class InitiateUploadResponse(BaseModel):
    """Initiate-upload response model."""

    model_config = ConfigDict(extra="forbid")

    strategy: UploadStrategy
    bucket: str
    key: str
    expires_in_seconds: int
    url: str | None = None
    upload_id: str | None = None
    part_size_bytes: int | None = None


class SignPartsRequest(BaseModel):
    """Multipart sign-parts request."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=2048)
    upload_id: str = Field(min_length=1, max_length=1024)
    part_numbers: list[Annotated[int, Field(ge=1, le=10_000)]] = Field(
        min_length=1,
        max_length=1000,
        json_schema_extra={"uniqueItems": True},
    )

    @field_validator("part_numbers")
    @classmethod
    def validate_part_numbers(cls, value: list[int]) -> list[int]:
        """Validate part numbers are unique and inside S3 bounds."""
        if len(value) != len(set(value)):
            raise ValueError("part_numbers must be unique")
        for number in value:
            if number < 1 or number > 10_000:
                raise ValueError("part_numbers must be between 1 and 10000")
        return value


class SignPartsResponse(BaseModel):
    """Multipart sign-parts response."""

    model_config = ConfigDict(extra="forbid")

    expires_in_seconds: int
    urls: dict[int, str]


class UploadedPart(BaseModel):
    """Part state returned for multipart upload introspection."""

    model_config = ConfigDict(extra="forbid")

    part_number: int = Field(ge=1, le=10_000)
    etag: str = Field(min_length=1, max_length=256)


class UploadIntrospectionRequest(BaseModel):
    """Multipart upload introspection request."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=2048)
    upload_id: str = Field(min_length=1, max_length=1024)


class UploadIntrospectionResponse(BaseModel):
    """Multipart upload introspection response."""

    model_config = ConfigDict(extra="forbid")

    bucket: str
    key: str
    upload_id: str
    part_size_bytes: int = Field(gt=0)
    parts: list[UploadedPart] = Field(max_length=10_000)


class CompletedPart(BaseModel):
    """Part metadata needed for multipart completion."""

    model_config = ConfigDict(extra="forbid")

    part_number: int = Field(ge=1, le=10_000)
    etag: str = Field(min_length=1, max_length=256)


class CompleteUploadRequest(BaseModel):
    """Multipart completion request."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=2048)
    upload_id: str = Field(min_length=1, max_length=1024)
    parts: list[CompletedPart] = Field(min_length=1, max_length=10_000)


class CompleteUploadResponse(BaseModel):
    """Multipart completion response."""

    model_config = ConfigDict(extra="forbid")

    bucket: str
    key: str
    etag: str | None = None
    version_id: str | None = None


class AbortUploadRequest(BaseModel):
    """Multipart abort request."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=2048)
    upload_id: str = Field(min_length=1, max_length=1024)


class AbortUploadResponse(BaseModel):
    """Multipart abort response."""

    model_config = ConfigDict(extra="forbid")

    ok: bool = True


class PresignDownloadRequest(BaseModel):
    """Presign download request."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=2048)
    content_disposition: str | None = Field(default=None, max_length=512)
    filename: str | None = Field(default=None, max_length=512)
    content_type: str | None = Field(default=None, max_length=256)


class PresignDownloadResponse(BaseModel):
    """Presign download response."""

    model_config = ConfigDict(extra="forbid")

    bucket: str
    key: str
    url: str
    expires_in_seconds: int


class CreateExportRequest(BaseModel):
    """Request payload for export creation."""

    model_config = ConfigDict(extra="forbid")

    source_key: str = Field(
        min_length=1,
        max_length=2048,
        description="Storage key of the source object to export.",
    )
    filename: str = Field(
        min_length=1,
        max_length=512,
        description="Client-facing filename to preserve in the export.",
    )


class ExportResource(BaseModel):
    """Public export workflow resource."""

    model_config = ConfigDict(extra="forbid")

    export_id: str
    source_key: str = Field(min_length=1, max_length=2048)
    filename: str = Field(min_length=1, max_length=512)
    status: ExportStatus
    output: ExportOutput | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: ExportRecord) -> ExportResource:
        """Project an internal record to the public export resource shape."""
        return cls(
            export_id=record.export_id,
            source_key=record.source_key,
            filename=record.filename,
            status=record.status,
            output=record.output,
            error=record.error,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class ExportListResponse(BaseModel):
    """Response payload for export listing endpoint."""

    model_config = ConfigDict(extra="forbid")

    exports: list[ExportResource] = Field(max_length=200)


class CapabilityDescriptor(BaseModel):
    """Machine-readable capability declaration."""

    model_config = ConfigDict(extra="forbid")

    key: str
    enabled: bool
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional capability metadata.",
    )


class CapabilitiesResponse(BaseModel):
    """Capabilities endpoint response."""

    model_config = ConfigDict(extra="forbid")

    capabilities: list[CapabilityDescriptor] = Field(max_length=256)


ResourceKey = Annotated[
    str,
    StringConstraints(min_length=1, max_length=256),
]


class ResourcePlanRequest(BaseModel):
    """Resource planning request body."""

    model_config = ConfigDict(extra="forbid")

    resources: list[ResourceKey] = Field(min_length=1, max_length=256)


class ResourcePlanItem(BaseModel):
    """Resource planning decision per requested resource."""

    model_config = ConfigDict(extra="forbid")

    resource: str
    supported: bool
    reason: str | None = None


class ResourcePlanResponse(BaseModel):
    """Resource planning response body."""

    model_config = ConfigDict(extra="forbid")

    plan: list[ResourcePlanItem] = Field(max_length=256)


class ReleaseInfoResponse(BaseModel):
    """Release metadata for conformance/debug clients."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    environment: str


class ErrorBody(BaseModel):
    """Standard API error body."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any]
    request_id: str | None


class ErrorEnvelope(BaseModel):
    """Standard API error envelope."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorBody


class HealthResponse(BaseModel):
    """Health endpoint response body."""

    model_config = ConfigDict(extra="forbid")

    ok: bool


class ReadinessResponse(BaseModel):
    """Readiness endpoint response body."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    checks: dict[str, bool]


class MetricsSummaryResponse(BaseModel):
    """Metrics summary endpoint response body."""

    model_config = ConfigDict(extra="forbid")

    counters: dict[str, int]
    latencies_ms: dict[str, float]
    activity: dict[str, int]
