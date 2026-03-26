"""AWS Lambda handlers for export Step Functions tasks."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from nova_file_api.config import Settings

from nova_workflows.models import ExportWorkflowInput
from nova_workflows.runtime import workflow_services
from nova_workflows.tasks import (
    copy_export,
    fail_export,
    finalize_export,
    validate_export,
)

_LOGGER = structlog.get_logger("nova_workflows.handlers")


def validate_export_handler(
    event: dict[str, Any],
    _context: object,
) -> dict[str, Any]:
    """Lambda handler for validating an export workflow input."""
    return asyncio.run(_validate_export(event=event))


def copy_export_handler(
    event: dict[str, Any],
    _context: object,
) -> dict[str, Any]:
    """Lambda handler for copying export data to its final location."""
    return asyncio.run(_copy_export(event=event))


def finalize_export_handler(
    event: dict[str, Any],
    _context: object,
) -> dict[str, Any]:
    """Lambda handler for marking an export as finalized and succeeded."""
    return asyncio.run(_finalize_export(event=event))


def fail_export_handler(
    event: dict[str, Any],
    _context: object,
) -> dict[str, Any]:
    """Lambda handler for persisting workflow failure state."""
    return asyncio.run(_fail_export(event=event))


async def _validate_export(*, event: dict[str, Any]) -> dict[str, Any]:
    workflow_input = ExportWorkflowInput.model_validate(event)
    _LOGGER.info(
        "workflow_validate_export_started",
        export_id=workflow_input.export_id,
        request_id=workflow_input.request_id,
    )
    async with workflow_services() as services:
        result = await validate_export(
            workflow_input=workflow_input,
            export_service=services.export_service,
        )
    return result.model_dump(mode="json")


async def _copy_export(*, event: dict[str, Any]) -> dict[str, Any]:
    workflow_input = ExportWorkflowInput.model_validate(event)
    _LOGGER.info(
        "workflow_copy_export_started",
        export_id=workflow_input.export_id,
        request_id=workflow_input.request_id,
    )
    settings = Settings()
    async with workflow_services(settings=settings) as services:
        result = await copy_export(
            workflow_input=workflow_input,
            export_service=services.export_service,
            transfer_service=services.transfer_service,
            file_transfer_bucket=settings.file_transfer_bucket,
        )
    return result.model_dump(mode="json")


async def _finalize_export(*, event: dict[str, Any]) -> dict[str, Any]:
    workflow_input = ExportWorkflowInput.model_validate(event)
    _LOGGER.info(
        "workflow_finalize_export_started",
        export_id=workflow_input.export_id,
        request_id=workflow_input.request_id,
    )
    async with workflow_services() as services:
        result = await finalize_export(
            workflow_input=workflow_input,
            export_service=services.export_service,
        )
    return result.model_dump(mode="json")


async def _fail_export(*, event: dict[str, Any]) -> dict[str, Any]:
    workflow_input = ExportWorkflowInput.model_validate(event)
    _LOGGER.warning(
        "workflow_fail_export_started",
        export_id=workflow_input.export_id,
        request_id=workflow_input.request_id,
        error=workflow_input.error,
    )
    async with workflow_services() as services:
        result = await fail_export(
            workflow_input=workflow_input,
            export_service=services.export_service,
        )
    return result.model_dump(mode="json")
