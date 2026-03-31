"""Pure async workflow task functions for export orchestration."""

from __future__ import annotations

from nova_file_api.exports import ExportService
from nova_file_api.models import ExportOutput, ExportStatus
from nova_file_api.transfer import ExportCopyResult, TransferService
from nova_workflows.models import ExportWorkflowInput, WorkflowOutput


async def validate_export(
    *,
    workflow_input: ExportWorkflowInput,
    export_service: ExportService,
) -> ExportWorkflowInput:
    """Mark an export as validating and pass the workflow input through."""
    await export_service.update_status(
        export_id=workflow_input.export_id,
        status=ExportStatus.VALIDATING,
        output=None,
        error=None,
    )
    return workflow_input


async def copy_export(
    *,
    workflow_input: ExportWorkflowInput,
    export_service: ExportService,
    transfer_service: TransferService,
    file_transfer_bucket: str,
) -> ExportWorkflowInput:
    """Copy upload content to the export location and return workflow output."""
    await export_service.update_status(
        export_id=workflow_input.export_id,
        status=ExportStatus.COPYING,
        output=None,
        error=None,
    )
    export_result = await transfer_service.copy_upload_to_export(
        source_bucket=file_transfer_bucket,
        source_key=workflow_input.source_key,
        scope_id=workflow_input.scope_id,
        export_id=workflow_input.export_id,
        filename=workflow_input.filename,
    )
    return workflow_input.model_copy(
        update={
            "output": WorkflowOutput.from_export_output(
                _export_output(export_result)
            )
        }
    )


async def finalize_export(
    *,
    workflow_input: ExportWorkflowInput,
    export_service: ExportService,
) -> ExportWorkflowInput:
    """Persist the finalizing and succeeded states for the export."""
    if workflow_input.output is None:
        raise ValueError("workflow output is required before finalization")
    output = workflow_input.output.to_export_output()
    await export_service.update_status(
        export_id=workflow_input.export_id,
        status=ExportStatus.FINALIZING,
        output=output,
        error=None,
    )
    await export_service.update_status(
        export_id=workflow_input.export_id,
        status=ExportStatus.SUCCEEDED,
        output=output,
        error=None,
    )
    return workflow_input


async def fail_export(
    *,
    workflow_input: ExportWorkflowInput,
    export_service: ExportService,
) -> ExportWorkflowInput:
    """Persist workflow failure status and error detail."""
    await export_service.update_status(
        export_id=workflow_input.export_id,
        status=ExportStatus.FAILED,
        output=None,
        error=workflow_input.failure_detail(),
    )
    return workflow_input


def _export_output(result: ExportCopyResult) -> ExportOutput:
    """Build the file API export output model from a copy result."""
    return ExportOutput(
        key=result.export_key,
        download_filename=result.download_filename,
    )
