"""Shared export workflow models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ExportStatus(StrEnum):
    """Lifecycle status of an export workflow."""

    QUEUED = "queued"
    VALIDATING = "validating"
    COPYING = "copying"
    FINALIZING = "finalizing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CopyStrategy(StrEnum):
    """Export copy execution lane persisted on the export record."""

    INLINE = "inline"
    WORKER = "worker"


class ExportOutput(BaseModel):
    """Completed export output metadata."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(
        min_length=1,
        max_length=2048,
        description="Storage key for the exported object.",
    )
    download_filename: str = Field(
        min_length=1,
        max_length=512,
        description="Filename presented to clients when downloading.",
    )


class ExportRecord(BaseModel):
    """Internal export workflow persistence record."""

    model_config = ConfigDict(extra="forbid")

    export_id: str
    scope_id: str
    request_id: str | None = None
    source_key: str = Field(min_length=1, max_length=2048)
    filename: str = Field(min_length=1, max_length=512)
    status: ExportStatus
    output: ExportOutput | None = None
    error: str | None = None
    execution_arn: str | None = None
    cancel_requested_at: datetime | None = None
    source_size_bytes: int | None = Field(default=None, ge=0)
    copy_strategy: CopyStrategy | None = None
    copy_export_key: str | None = Field(
        default=None, min_length=1, max_length=2048
    )
    copy_upload_id: str | None = Field(
        default=None, min_length=1, max_length=1024
    )
    copy_part_size_bytes: int | None = Field(default=None, gt=0)
    copy_part_count: int | None = Field(default=None, gt=0)
    copying_entered_at: datetime | None = None
    finalizing_entered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
