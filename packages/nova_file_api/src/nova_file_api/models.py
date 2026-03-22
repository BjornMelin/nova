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


class UploadStrategy(StrEnum):
    """Upload strategy options returned by initiate endpoint."""

    SINGLE = "single"
    MULTIPART = "multipart"


class AuthMode(StrEnum):
    """Authentication modes supported by the API."""

    JWT_LOCAL = "jwt_local"


class JobsQueueBackend(StrEnum):
    """Queue backends available for async jobs."""

    MEMORY = "memory"
    SQS = "sqs"


class JobsRepositoryBackend(StrEnum):
    """Repository backends available for async job persistence."""

    MEMORY = "memory"
    DYNAMODB = "dynamodb"


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


class EnqueueJobRequest(BaseModel):
    """Request payload for job enqueue endpoint."""

    model_config = ConfigDict(extra="forbid")

    job_type: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)


TRANSFER_PROCESS_JOB_TYPE = "transfer.process"


class JobStatus(StrEnum):
    """Lifecycle status of an async job."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class JobRecord(BaseModel):
    """Persistent job representation."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    job_type: str
    scope_id: str
    status: JobStatus
    payload: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class EnqueueJobResponse(BaseModel):
    """Response payload for enqueue endpoint."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    """Response payload for status endpoint."""

    model_config = ConfigDict(extra="forbid")

    job: JobRecord


class JobCancelResponse(BaseModel):
    """Response payload for cancel endpoint."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: JobStatus


class JobListResponse(BaseModel):
    """Response payload for job listing endpoint."""

    model_config = ConfigDict(extra="forbid")

    jobs: list[JobRecord] = Field(max_length=200)


class JobEventType(StrEnum):
    """Event kinds emitted by the v1 job events contract."""

    SNAPSHOT = "snapshot"


class JobEvent(BaseModel):
    """Single event entry for a job event stream/poll response."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    job_id: str
    status: JobStatus
    event_type: JobEventType = JobEventType.SNAPSHOT
    timestamp: datetime
    data: dict[str, Any] = Field(default_factory=dict)


class JobEventsResponse(BaseModel):
    """Polling/SSE-compatible events response envelope."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    events: list[JobEvent] = Field(max_length=1000)
    next_cursor: str


class CapabilityDescriptor(BaseModel):
    """Machine-readable capability declaration."""

    model_config = ConfigDict(extra="forbid")

    key: str
    enabled: bool
    details: dict[str, Any] = Field(default_factory=dict)


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
