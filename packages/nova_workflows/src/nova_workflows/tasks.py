"""Pure async workflow task functions for export orchestration."""

from __future__ import annotations

from typing import Protocol

from nova_file_api.export_models import (
    ExportOutput,
    ExportRecord,
    ExportStatus,
)
from nova_file_api.workflow_facade import (
    ExportCopyPollResult,
    ExportCopyResult,
    ExportCopyStrategy,
    ExportStatusTransitionError,
    ExportTransferService,
    PreparedExportCopy,
    QueuedExportCopyState,
    WorkflowExportStateService,
)
from nova_workflows.models import ExportWorkflowInput, WorkflowOutput


class ExportCopyCoordinator(Protocol):
    """Subset of the large export-copy coordinator used by workflow tasks."""

    async def prepare(self, *, export: ExportRecord) -> PreparedExportCopy:
        """Resolve one export-copy execution plan."""
        ...

    async def start(
        self,
        *,
        export: ExportRecord,
        prepared: PreparedExportCopy,
    ) -> QueuedExportCopyState:
        """Persist part state and enqueue queued copy work."""
        ...

    async def poll(
        self,
        *,
        export: ExportRecord,
        upload_id: str,
        export_key: str,
        download_filename: str,
    ) -> ExportCopyPollResult:
        """Poll queued copy progress and finalize the destination MPU."""
        ...

    async def abort_upload(
        self,
        *,
        upload_id: str,
        export_key: str,
    ) -> None:
        """Abort one queued copy MPU during rollback."""
        ...


async def validate_export(
    *,
    workflow_input: ExportWorkflowInput,
    export_service: WorkflowExportStateService,
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
    export_service: WorkflowExportStateService,
    transfer_service: ExportTransferService,
    file_transfer_bucket: str,
) -> ExportWorkflowInput:
    """Copy upload content to the export location and return workflow output."""
    export = await export_service.repository.get(workflow_input.export_id)
    if export is None:
        raise LookupError("export not found")
    if export.status == ExportStatus.CANCELLED:
        return _cancelled_workflow_input(workflow_input=workflow_input)
    try:
        await export_service.update_status(
            export_id=workflow_input.export_id,
            status=ExportStatus.COPYING,
            output=None,
            error=None,
        )
    except ExportStatusTransitionError:
        latest = await export_service.repository.get(workflow_input.export_id)
        if latest is not None and latest.status == ExportStatus.CANCELLED:
            return _cancelled_workflow_input(workflow_input=workflow_input)
        raise
    export_result = await transfer_service.copy_upload_to_export(
        source_bucket=file_transfer_bucket,
        source_key=workflow_input.source_key,
        scope_id=workflow_input.scope_id,
        export_id=workflow_input.export_id,
        filename=workflow_input.filename,
    )
    latest = await export_service.repository.get(workflow_input.export_id)
    if latest is None:
        raise LookupError("export not found")
    if latest.status == ExportStatus.CANCELLED:
        await transfer_service.delete_export_object(
            export_key=export_result.export_key
        )
        return _cancelled_workflow_input(workflow_input=workflow_input)
    return workflow_input.model_copy(
        update={
            "output": WorkflowOutput.from_export_output(
                _export_output(export_result)
            ),
            "copy_progress_state": "ready",
        }
    )


async def prepare_export_copy(
    *,
    workflow_input: ExportWorkflowInput,
    export_service: WorkflowExportStateService,
    large_copy_service: ExportCopyCoordinator,
) -> ExportWorkflowInput:
    """Resolve export-copy strategy and persist internal copy metadata."""
    export = await export_service.repository.get(workflow_input.export_id)
    if export is None:
        raise LookupError("export not found")
    prepared = await large_copy_service.prepare(export=export)
    updated_record = export.model_copy(
        update={
            "source_size_bytes": prepared.source_size_bytes,
            "copy_strategy": prepared.strategy.value,
            "copy_export_key": prepared.export_key,
            "copy_part_size_bytes": prepared.copy_part_size_bytes,
            "copy_part_count": prepared.copy_part_count,
        }
    )
    updated_ok = await export_service.repository.update_if_status(
        record=updated_record,
        expected_status=export.status,
    )
    if not updated_ok:
        latest = await export_service.repository.get(workflow_input.export_id)
        if latest is not None and latest.status == ExportStatus.CANCELLED:
            return _cancelled_workflow_input(workflow_input=workflow_input)
        if latest is None or latest.status != ExportStatus.CANCELLED:
            raise RuntimeError(
                "export copy planning changed before state could persist"
            )
    return workflow_input.model_copy(
        update={
            "source_size_bytes": prepared.source_size_bytes,
            "copy_strategy": prepared.strategy.value,
            "copy_export_key": prepared.export_key,
            "copy_part_size_bytes": prepared.copy_part_size_bytes,
            "copy_part_count": prepared.copy_part_count,
            "output": WorkflowOutput(
                key=prepared.export_key,
                download_filename=prepared.download_filename,
            ),
        }
    )


async def start_queued_export_copy(
    *,
    workflow_input: ExportWorkflowInput,
    export_service: WorkflowExportStateService,
    large_copy_service: ExportCopyCoordinator,
) -> ExportWorkflowInput:
    """Create the worker-lane MPU, persist part state, and enqueue work."""
    if workflow_input.copy_progress_state == "cancelled":
        return _cancelled_workflow_input(workflow_input=workflow_input)
    export = await export_service.repository.get(workflow_input.export_id)
    if export is None:
        raise LookupError("export not found")
    if export.status == ExportStatus.CANCELLED:
        return _cancelled_workflow_input(workflow_input=workflow_input)
    if workflow_input.output is None:
        raise ValueError(
            "workflow output is required before queueing copy work"
        )
    prepared = _prepared_export_copy(workflow_input=workflow_input)
    if prepared.strategy != ExportCopyStrategy.WORKER:
        return workflow_input.model_copy(
            update={"copy_progress_state": "ready"}
        )
    queued = await large_copy_service.start(export=export, prepared=prepared)
    try:
        copying_record = await export_service.update_status(
            export_id=workflow_input.export_id,
            status=ExportStatus.COPYING,
            output=None,
            error=None,
        )
    except ExportStatusTransitionError:
        await large_copy_service.abort_upload(
            upload_id=queued.upload_id,
            export_key=queued.export_key,
        )
        latest = await export_service.repository.get(workflow_input.export_id)
        if latest is not None and latest.status == ExportStatus.CANCELLED:
            return _cancelled_workflow_input(workflow_input=workflow_input)
        raise
    updated_record = copying_record.model_copy(
        update={
            "source_size_bytes": prepared.source_size_bytes,
            "copy_strategy": prepared.strategy.value,
            "copy_export_key": queued.export_key,
            "copy_upload_id": queued.upload_id,
            "copy_part_size_bytes": queued.copy_part_size_bytes,
            "copy_part_count": queued.copy_part_count,
        }
    )
    updated_ok = await export_service.repository.update_if_status(
        record=updated_record,
        expected_status=copying_record.status,
    )
    if not updated_ok:
        latest = await export_service.repository.get(workflow_input.export_id)
        if latest is not None and latest.status == ExportStatus.CANCELLED:
            await large_copy_service.abort_upload(
                upload_id=queued.upload_id,
                export_key=queued.export_key,
            )
            return _cancelled_workflow_input(workflow_input=workflow_input)
        if latest is None or latest.status != ExportStatus.CANCELLED:
            raise RuntimeError(
                "export copy metadata changed before queued state could persist"
            )
    return workflow_input.model_copy(
        update={
            "copy_strategy": prepared.strategy.value,
            "copy_export_key": queued.export_key,
            "copy_upload_id": queued.upload_id,
            "copy_part_size_bytes": queued.copy_part_size_bytes,
            "copy_part_count": queued.copy_part_count,
            "copy_progress_state": "pending",
            "copy_completed_parts": 0,
            "copy_total_parts": queued.copy_part_count,
        }
    )


async def poll_queued_export_copy(
    *,
    workflow_input: ExportWorkflowInput,
    export_service: WorkflowExportStateService,
    large_copy_service: ExportCopyCoordinator,
) -> ExportWorkflowInput:
    """Poll queued part-copy progress and finalize the MPU when complete."""
    export = await export_service.repository.get(workflow_input.export_id)
    if export is None:
        raise LookupError("export not found")
    if workflow_input.output is None:
        raise ValueError("workflow output is required before polling copy work")
    if (
        workflow_input.copy_upload_id is None
        or workflow_input.copy_export_key is None
    ):
        raise ValueError("queued copy context is missing")
    polled = await large_copy_service.poll(
        export=export,
        upload_id=workflow_input.copy_upload_id,
        export_key=workflow_input.copy_export_key,
        download_filename=workflow_input.output.download_filename,
    )
    update: dict[str, object] = {
        "copy_progress_state": polled.state,
        "copy_completed_parts": polled.completed_parts,
        "copy_total_parts": polled.total_parts,
    }
    if polled.output_key is not None and polled.download_filename is not None:
        update["output"] = WorkflowOutput(
            key=polled.output_key,
            download_filename=polled.download_filename,
        )
    return workflow_input.model_copy(update=update)


async def finalize_export(
    *,
    workflow_input: ExportWorkflowInput,
    export_service: WorkflowExportStateService,
) -> ExportWorkflowInput:
    """Persist the finalizing and succeeded states for the export."""
    export = await export_service.repository.get(workflow_input.export_id)
    if export is None:
        raise LookupError("export not found")
    if export.status == ExportStatus.CANCELLED:
        return _cancelled_workflow_input(
            workflow_input=workflow_input,
            status=ExportStatus.CANCELLED,
        )
    if workflow_input.output is None:
        raise ValueError("workflow output is required before finalization")
    output = workflow_input.output.to_export_output()
    try:
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
    except ExportStatusTransitionError:
        latest = await export_service.repository.get(workflow_input.export_id)
        if latest is not None and latest.status == ExportStatus.CANCELLED:
            return _cancelled_workflow_input(
                workflow_input=workflow_input,
                status=ExportStatus.CANCELLED,
            )
        raise
    return workflow_input.model_copy(update={"status": ExportStatus.SUCCEEDED})


async def fail_export(
    *,
    workflow_input: ExportWorkflowInput,
    export_service: WorkflowExportStateService,
) -> ExportWorkflowInput:
    """Persist workflow failure status and error detail."""
    export = await export_service.repository.get(workflow_input.export_id)
    if export is None:
        raise LookupError("export not found")
    if export.status == ExportStatus.CANCELLED:
        return _cancelled_workflow_input(
            workflow_input=workflow_input,
            status=ExportStatus.CANCELLED,
        )
    try:
        await export_service.update_status(
            export_id=workflow_input.export_id,
            status=ExportStatus.FAILED,
            output=None,
            error=workflow_input.failure_detail(),
        )
    except ExportStatusTransitionError:
        latest = await export_service.repository.get(workflow_input.export_id)
        if latest is not None and latest.status == ExportStatus.CANCELLED:
            return _cancelled_workflow_input(
                workflow_input=workflow_input,
                status=ExportStatus.CANCELLED,
            )
        raise
    return workflow_input.model_copy(update={"status": ExportStatus.FAILED})


def _export_output(result: ExportCopyResult) -> ExportOutput:
    """Build the file API export output model from a copy result."""
    return ExportOutput(
        key=result.export_key,
        download_filename=result.download_filename,
    )


def _cancelled_workflow_input(
    *,
    workflow_input: ExportWorkflowInput,
    status: ExportStatus | None = None,
) -> ExportWorkflowInput:
    """Return one cancelled workflow payload with stale output cleared."""
    update: dict[str, object] = {
        "copy_progress_state": "cancelled",
        "output": None,
    }
    if status is not None:
        update["status"] = status
    return workflow_input.model_copy(update=update)


def _prepared_export_copy(
    *,
    workflow_input: ExportWorkflowInput,
) -> PreparedExportCopy:
    if (
        workflow_input.output is None
        or workflow_input.source_size_bytes is None
        or workflow_input.copy_part_size_bytes is None
        or workflow_input.copy_part_count is None
        or workflow_input.copy_strategy is None
    ):
        raise ValueError(
            "prepared queued export copy state is missing from workflow input"
        )
    try:
        strategy = ExportCopyStrategy(workflow_input.copy_strategy)
    except ValueError as exc:
        raise ValueError(
            f"invalid copy_strategy: {workflow_input.copy_strategy}"
        ) from exc
    return PreparedExportCopy(
        export_key=workflow_input.output.key,
        download_filename=workflow_input.output.download_filename,
        source_size_bytes=workflow_input.source_size_bytes,
        copy_part_size_bytes=workflow_input.copy_part_size_bytes,
        copy_part_count=workflow_input.copy_part_count,
        strategy=strategy,
    )
