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
    model_validator,
)

from nova_file_api.export_models import (
    ExportDownloadFilename,
    ExportOutput,
    ExportRecord,
    ExportStatus,
    ExportStorageKey,
)
from nova_file_api.transfer_policy import ChecksumMode
from nova_file_api.upload_sessions import UploadStrategy


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
    """Initiate-upload request model.

    Client hints (``workload_class``, ``policy_hint``, ``checksum_preference``)
    are inputs only. The effective persisted transfer policy exposes
    ``checksum_mode`` as ``none|optional|required`` per SPEC-0002 (S3
    integration). ``checksum_preference`` accepts ``none|standard|strict`` as a
    client preference; preference is not the same enum as mode mapping and the
    final mode decision happens server-side.
    """

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(
        min_length=1,
        max_length=512,
        description="Client-facing filename for the object being uploaded.",
    )
    content_type: str | None = Field(
        default=None,
        max_length=256,
        description=(
            "Optional MIME type that should be persisted with the object."
        ),
    )
    size_bytes: int = Field(
        gt=0,
        description="Total size of the object being uploaded, in bytes.",
    )
    workload_class: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description=(
            "Optional workload-class hint for transfer policy selection."
        ),
    )
    policy_hint: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Optional transfer-policy hint evaluated by the API.",
    )
    # Client preference (none|standard|strict); server maps to checksum_mode
    # (SPEC-0002).
    checksum_preference: str | None = Field(
        default=None,
        pattern="^(none|standard|strict)$",
        description="Preferred checksum strictness requested by the client.",
    )
    checksum_value: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description=(
            "Optional checksum value supplied with the initiate request."
        ),
    )


class InitiateUploadResponse(BaseModel):
    """Initiate-upload response model."""

    model_config = ConfigDict(extra="forbid")

    strategy: UploadStrategy = Field(
        description="Upload strategy selected by the API for this transfer."
    )
    bucket: str = Field(
        description="Bucket that will receive the uploaded object."
    )
    key: str = Field(
        description="Storage key reserved for the uploaded object."
    )
    session_id: str = Field(
        description="Durable upload-session identifier used for resume flows."
    )
    expires_in_seconds: int = Field(
        description="Seconds until the returned presigned inputs expire."
    )
    policy_id: str = Field(
        description="Identifier of the effective transfer policy."
    )
    policy_version: str = Field(
        description="Version of the effective transfer policy."
    )
    max_concurrency_hint: int = Field(
        description="Suggested maximum number of concurrent client uploads."
    )
    sign_batch_size_hint: int = Field(
        description="Suggested maximum number of parts per sign-parts request."
    )
    accelerate_enabled: bool = Field(
        description=(
            "Whether S3 Transfer Acceleration is enabled for the session."
        )
    )
    checksum_algorithm: str | None = Field(
        default=None,
        description=(
            "Checksum algorithm callers should use when checksums apply."
        ),
    )
    checksum_mode: ChecksumMode = Field(
        description="Server-resolved checksum enforcement mode for the upload."
    )
    resumable_until: datetime = Field(
        description=(
            "Timestamp until which multipart resume operations are valid."
        )
    )
    url: str | None = Field(
        default=None,
        description=(
            "Presigned single-part upload URL when the strategy is direct."
        ),
    )
    upload_id: str | None = Field(
        default=None,
        description=(
            "S3 multipart upload identifier when multipart is required."
        ),
    )
    part_size_bytes: int | None = Field(
        default=None,
        description=(
            "Target multipart part size in bytes when multipart is required."
        ),
    )


class SignPartsRequest(BaseModel):
    """Multipart sign-parts request."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(
        min_length=1,
        max_length=2048,
        description="Storage key reserved for the multipart upload.",
    )
    upload_id: str = Field(
        min_length=1,
        max_length=1024,
        description=(
            "S3 multipart upload identifier returned by initiate upload."
        ),
    )
    part_numbers: list[Annotated[int, Field(ge=1, le=10_000)]] = Field(
        min_length=1,
        max_length=1000,
        json_schema_extra={"uniqueItems": True},
        description="Multipart part numbers to sign in this request.",
    )
    checksums_sha256: dict[int, str] | None = Field(
        default=None,
        description=(
            "Optional SHA-256 checksum map keyed by multipart part number."
        ),
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

    @field_validator("checksums_sha256")
    @classmethod
    def validate_checksums_sha256(
        cls, value: dict[int, str] | None
    ) -> dict[int, str] | None:
        """Validate optional SHA-256 checksum map shape."""
        if value is None:
            return None
        normalized: dict[int, str] = {}
        for raw_part_number, checksum in value.items():
            if raw_part_number < 1 or raw_part_number > 10_000:
                raise ValueError(
                    "checksum part numbers must be between 1 and 10000"
                )
            stripped = checksum.strip()
            if not stripped:
                raise ValueError("checksum values must be non-empty")
            normalized[int(raw_part_number)] = stripped
        return normalized


class SignPartsResponse(BaseModel):
    """Multipart sign-parts response."""

    model_config = ConfigDict(extra="forbid")

    expires_in_seconds: int = Field(
        description="Seconds until the presigned part URLs expire."
    )
    urls: dict[int, str] = Field(
        description=(
            "Presigned upload URL for each requested multipart part number."
        )
    )


class UploadedPart(BaseModel):
    """Part state returned for multipart upload introspection."""

    model_config = ConfigDict(extra="forbid")

    part_number: int = Field(
        ge=1,
        le=10_000,
        description="Multipart part number that has already been uploaded.",
    )
    etag: str = Field(
        min_length=1,
        max_length=256,
        description="ETag returned by S3 for the uploaded multipart part.",
    )


class UploadIntrospectionRequest(BaseModel):
    """Multipart upload introspection request."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(
        min_length=1,
        max_length=2048,
        description="Storage key reserved for the multipart upload.",
    )
    upload_id: str = Field(
        min_length=1,
        max_length=1024,
        description="S3 multipart upload identifier being inspected.",
    )


class UploadIntrospectionResponse(BaseModel):
    """Multipart upload introspection response."""

    model_config = ConfigDict(extra="forbid")

    bucket: str = Field(description="Bucket that owns the multipart upload.")
    key: str = Field(
        description="Storage key reserved for the multipart upload."
    )
    upload_id: str = Field(description="S3 multipart upload identifier.")
    part_size_bytes: int = Field(
        gt=0,
        description="Configured multipart part size in bytes for this session.",
    )
    parts: list[UploadedPart] = Field(
        max_length=10_000,
        description="Multipart parts that have already been uploaded.",
    )


class CompletedPart(BaseModel):
    """Part metadata needed for multipart completion."""

    model_config = ConfigDict(extra="forbid")

    part_number: int = Field(
        ge=1,
        le=10_000,
        description="Multipart part number included in the completion request.",
    )
    etag: str = Field(
        min_length=1,
        max_length=256,
        description="ETag returned by S3 for the completed multipart part.",
    )
    checksum_sha256: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description=(
            "Optional SHA-256 checksum for the completed multipart part."
        ),
    )


class CompleteUploadRequest(BaseModel):
    """Multipart completion request."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(
        min_length=1,
        max_length=2048,
        description="Storage key reserved for the multipart upload.",
    )
    upload_id: str = Field(
        min_length=1,
        max_length=1024,
        description="S3 multipart upload identifier being finalized.",
    )
    parts: list[CompletedPart] = Field(
        min_length=1,
        max_length=10_000,
        description="Ordered multipart parts to finalize in S3.",
    )

    @model_validator(mode="after")
    def validate_checksum_part_sequence(self) -> CompleteUploadRequest:
        """Require contiguous part numbers when checksum values are present."""
        if not any(part.checksum_sha256 is not None for part in self.parts):
            return self
        actual = [part.part_number for part in self.parts]
        expected = list(range(1, len(self.parts) + 1))
        if actual != expected:
            raise ValueError(
                "parts must be consecutive and start at 1 when "
                "checksum_sha256 is provided"
            )
        return self


class CompleteUploadResponse(BaseModel):
    """Multipart completion response."""

    model_config = ConfigDict(extra="forbid")

    bucket: str = Field(
        description="Bucket that now contains the completed object."
    )
    key: str = Field(description="Storage key of the completed object.")
    etag: str | None = Field(
        default=None,
        description="Object ETag returned by S3 when available.",
    )
    version_id: str | None = Field(
        default=None,
        description=(
            "S3 object version identifier when bucket versioning is enabled."
        ),
    )


class AbortUploadRequest(BaseModel):
    """Multipart abort request."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(
        min_length=1,
        max_length=2048,
        description="Storage key reserved for the multipart upload.",
    )
    upload_id: str = Field(
        min_length=1,
        max_length=1024,
        description="S3 multipart upload identifier being aborted.",
    )


class AbortUploadResponse(BaseModel):
    """Multipart abort response."""

    model_config = ConfigDict(extra="forbid")

    ok: bool = Field(
        default=True,
        description="Whether the multipart abort request was accepted.",
    )


class PresignDownloadRequest(BaseModel):
    """Presign download request."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(
        min_length=1,
        max_length=2048,
        description="Storage key of the object to download.",
    )
    content_disposition: str | None = Field(
        default=None,
        max_length=512,
        description=(
            "Optional Content-Disposition override for the download response."
        ),
    )
    filename: str | None = Field(
        default=None,
        max_length=512,
        description="Optional filename hint applied to Content-Disposition.",
    )
    content_type: str | None = Field(
        default=None,
        max_length=256,
        description="Optional Content-Type override for the download response.",
    )


class PresignDownloadResponse(BaseModel):
    """Presign download response."""

    model_config = ConfigDict(extra="forbid")

    bucket: str = Field(description="Bucket that owns the downloadable object.")
    key: str = Field(description="Storage key of the downloadable object.")
    url: str = Field(
        description="Presigned download URL for the requested object."
    )
    expires_in_seconds: int = Field(
        description="Seconds until the presigned download URL expires."
    )


class CreateExportRequest(BaseModel):
    """Request payload for export creation."""

    model_config = ConfigDict(extra="forbid")

    source_key: ExportStorageKey = Field(
        description="Storage key of the source object to export.",
    )
    filename: ExportDownloadFilename = Field(
        description="Client-facing filename to preserve in the export.",
    )


class ExportResource(BaseModel):
    """Public export workflow resource."""

    model_config = ConfigDict(extra="forbid")

    export_id: str = Field(
        description="Identifier of the caller-owned export workflow resource."
    )
    source_key: ExportStorageKey
    filename: ExportDownloadFilename
    status: ExportStatus = Field(
        description="Current lifecycle state of the export workflow."
    )
    output: ExportOutput | None = Field(
        default=None,
        description="Completed output metadata when the export succeeds.",
    )
    error: str | None = Field(
        default=None,
        description="Terminal error message when the export fails.",
    )
    execution_arn: str | None = Field(
        default=None,
        description=(
            "Step Functions execution ARN for the active export workflow."
        ),
    )
    cancel_requested_at: datetime | None = Field(
        default=None,
        description=(
            "Timestamp when cancel intent was persisted for the export."
        ),
    )
    created_at: datetime = Field(
        description="Timestamp when the export workflow resource was created."
    )
    updated_at: datetime = Field(
        description="Timestamp when the export workflow resource last changed."
    )

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
            execution_arn=record.execution_arn,
            cancel_requested_at=record.cancel_requested_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class ExportListResponse(BaseModel):
    """Response payload for export listing endpoint."""

    model_config = ConfigDict(extra="forbid")

    exports: list[ExportResource] = Field(
        max_length=200,
        description=(
            "Caller-owned export workflow resources ordered by recency."
        ),
    )


class CapabilityDescriptor(BaseModel):
    """Machine-readable capability declaration."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(description="Stable capability identifier.")
    enabled: bool = Field(
        description=(
            "Whether the capability is enabled in the current deployment."
        )
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional capability metadata.",
    )


class CapabilitiesResponse(BaseModel):
    """Capabilities endpoint response."""

    model_config = ConfigDict(extra="forbid")

    capabilities: list[CapabilityDescriptor] = Field(
        max_length=256,
        description="Capability declarations exposed by the running API.",
    )


class TransferCapabilitiesResponse(BaseModel):
    """Transfer policy capabilities exposed to clients and operators."""

    model_config = ConfigDict(extra="forbid")

    policy_id: str = Field(
        description="Identifier of the effective transfer policy."
    )
    policy_version: str = Field(
        description="Version of the effective transfer policy."
    )
    max_upload_bytes: int = Field(
        description="Maximum allowed upload size in bytes."
    )
    multipart_threshold_bytes: int = Field(
        description=(
            "Object size in bytes at which multipart upload becomes required."
        )
    )
    target_upload_part_count: int = Field(
        description="Target number of multipart parts for large uploads."
    )
    minimum_part_size_bytes: int = Field(
        description="Minimum multipart part size accepted by the API."
    )
    maximum_part_size_bytes: int = Field(
        description="Maximum multipart part size accepted by the API."
    )
    max_concurrency_hint: int = Field(
        description="Suggested maximum number of concurrent client uploads."
    )
    sign_batch_size_hint: int = Field(
        description="Suggested maximum number of parts per sign-parts request."
    )
    accelerate_enabled: bool = Field(
        description="Whether S3 Transfer Acceleration is enabled."
    )
    checksum_algorithm: str | None = Field(
        default=None,
        description=(
            "Checksum algorithm callers should use when checksums apply."
        ),
    )
    checksum_mode: ChecksumMode = Field(
        description="Server-enforced checksum mode for uploads."
    )
    resumable_ttl_seconds: int = Field(
        description="How long multipart resume state remains valid, in seconds."
    )
    active_multipart_upload_limit: int = Field(
        description="Maximum number of active multipart uploads per scope."
    )
    daily_ingress_budget_bytes: int = Field(
        description="Per-scope daily ingress budget in bytes."
    )
    sign_requests_per_upload_limit: int = Field(
        description="Maximum number of sign-parts requests allowed per upload."
    )
    large_export_worker_threshold_bytes: int = Field(
        description=(
            "Export size threshold in bytes for the worker-backed copy lane."
        )
    )


ResourceKey = Annotated[
    str,
    StringConstraints(min_length=1, max_length=256),
    Field(description="Public resource key evaluated by the resource planner."),
]


class ResourcePlanRequest(BaseModel):
    """Resource planning request body."""

    model_config = ConfigDict(extra="forbid")

    resources: list[ResourceKey] = Field(
        min_length=1,
        max_length=256,
        description="Resource keys whose supportability should be evaluated.",
    )


class ResourcePlanItem(BaseModel):
    """Resource planning decision per requested resource."""

    model_config = ConfigDict(extra="forbid")

    resource: str = Field(description="Requested resource key.")
    supported: bool = Field(
        description=(
            "Whether the resource is supported in the current deployment."
        )
    )
    reason: str | None = Field(
        default=None,
        description=(
            "Machine-readable reason when the resource is not supported."
        ),
    )


class ResourcePlanResponse(BaseModel):
    """Resource planning response body."""

    model_config = ConfigDict(extra="forbid")

    plan: list[ResourcePlanItem] = Field(
        max_length=256,
        description="Supportability decision for each requested resource key.",
    )


class ReleaseInfoResponse(BaseModel):
    """Release metadata for conformance/debug clients."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Public application name for the deployment.")
    version: str = Field(description="Published application version string.")
    environment: str = Field(description="Deployment environment name.")


class ErrorBody(BaseModel):
    """Standard API error body."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(description="Stable machine-readable error code.")
    message: str = Field(description="Human-readable error summary.")
    details: dict[str, Any] = Field(
        description="Additional structured details for the error."
    )
    request_id: str | None = Field(
        description=(
            "Request identifier associated with the failure when available."
        )
    )


class ErrorEnvelope(BaseModel):
    """Standard API error envelope."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorBody = Field(description="Standard API error payload.")


class HealthResponse(BaseModel):
    """Health endpoint response body."""

    model_config = ConfigDict(extra="forbid")

    ok: bool = Field(description="Whether the runtime process is alive.")


class ReadinessResponse(BaseModel):
    """Readiness endpoint response body."""

    model_config = ConfigDict(extra="forbid")

    ok: bool = Field(
        description="Whether every required traffic dependency is ready."
    )
    checks: dict[str, bool] = Field(
        description="Per-dependency readiness results keyed by check name."
    )


class MetricsSummaryResponse(BaseModel):
    """Metrics summary endpoint response body."""

    model_config = ConfigDict(extra="forbid")

    counters: dict[str, int] = Field(
        description="Low-cardinality request and workflow counters."
    )
    latencies_ms: dict[str, float] = Field(
        description="Aggregated request-latency summaries in milliseconds."
    )
    activity: dict[str, int] = Field(
        description="Activity rollups derived from the activity store."
    )
