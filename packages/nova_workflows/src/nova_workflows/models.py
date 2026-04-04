"""Workflow models for Step Functions export orchestration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from nova_runtime_support.export_models import ExportOutput, ExportStatus


class WorkflowOutput(BaseModel):
    """Serializable export output passed between workflow tasks."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=2048)
    download_filename: str = Field(min_length=1, max_length=512)

    @classmethod
    def from_export_output(cls, output: ExportOutput) -> WorkflowOutput:
        """Build a workflow output model from the file API export output."""
        return cls(
            key=output.key,
            download_filename=output.download_filename,
        )

    def to_export_output(self) -> ExportOutput:
        """Convert the workflow output to the file API export output model."""
        return ExportOutput(
            key=self.key,
            download_filename=self.download_filename,
        )


class ExportWorkflowInput(BaseModel):
    """Normalized Step Functions payload for export workflows."""

    model_config = ConfigDict(extra="forbid")

    export_id: str = Field(min_length=1, max_length=128)
    scope_id: str = Field(min_length=1, max_length=256)
    source_key: str = Field(min_length=1, max_length=2048)
    filename: str = Field(min_length=1, max_length=512)
    request_id: str | None = Field(default=None, max_length=256)
    status: ExportStatus
    created_at: str = Field(min_length=1, max_length=128)
    updated_at: str = Field(min_length=1, max_length=128)
    output: WorkflowOutput | None = None
    source_size_bytes: int | None = Field(default=None, ge=1)
    copy_strategy: str | None = Field(default=None, max_length=32)
    copy_export_key: str | None = Field(default=None, max_length=2048)
    copy_upload_id: str | None = Field(default=None, max_length=1024)
    copy_part_size_bytes: int | None = Field(default=None, ge=1)
    copy_part_count: int | None = Field(default=None, ge=1)
    copy_progress_state: str | None = Field(default=None, max_length=32)
    copy_completed_parts: int | None = Field(default=None, ge=0)
    copy_total_parts: int | None = Field(default=None, ge=1)
    error: str | None = Field(default=None, max_length=256)
    cause: str | None = Field(default=None, max_length=4000)

    def failure_detail(self) -> str:
        """Return the operator-facing failure detail for a failed workflow."""
        if self.cause and self.cause.strip():
            return self.cause.strip()
        if self.error and self.error.strip():
            return self.error.strip()
        return "export workflow failed"
