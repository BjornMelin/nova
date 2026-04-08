"""AWS Lambda handlers for export Step Functions tasks."""

from __future__ import annotations

import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any, cast

import aioboto3
import structlog

from nova_file_api.workflow_facade import (
    ExportCopyPoisonMessage,
    ExportCopyTaskMessage,
    TransferReconciliationConfig,
    TransferReconciliationService,
    TransferUsageDynamoResource,
    UploadSessionDynamoResource,
    aws_client_config,
    build_transfer_usage_window_repository,
    build_upload_session_repository,
    s3_client_config,
)
from nova_workflows.models import ExportWorkflowInput
from nova_workflows.runtime import export_services, workflow_services
from nova_workflows.tasks import (
    copy_export,
    fail_export,
    finalize_export,
    poll_queued_export_copy,
    prepare_export_copy,
    start_queued_export_copy,
    validate_export,
)
from nova_workflows.workflow_config import WorkflowSettings

_LOGGER = structlog.get_logger("nova_workflows.handlers")


def validate_export_handler(
    event: dict[str, Any],
    _context: object,
) -> dict[str, Any]:
    """Validate export input and let model validation errors propagate.

    ValidationError raised by _validate_export via model_validate is
    intentionally not caught here so Step Functions catchers can handle
    malformed input.
    """
    return asyncio.run(_validate_export(event=event))


def copy_export_handler(
    event: dict[str, Any],
    _context: object,
) -> dict[str, Any]:
    """Lambda handler for copying export data to its final location."""
    return asyncio.run(_copy_export(event=event))


def prepare_export_copy_handler(
    event: dict[str, Any],
    _context: object,
) -> dict[str, Any]:
    """Lambda handler for export-copy planning."""
    return asyncio.run(_prepare_export_copy(event=event))


def start_queued_export_copy_handler(
    event: dict[str, Any],
    _context: object,
) -> dict[str, Any]:
    """Lambda handler for large export queue initialization."""
    return asyncio.run(_start_queued_export_copy(event=event))


def poll_queued_export_copy_handler(
    event: dict[str, Any],
    _context: object,
) -> dict[str, Any]:
    """Lambda handler for queued export-copy polling/finalization."""
    return asyncio.run(_poll_queued_export_copy(event=event))


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


def reconcile_transfer_state_handler(
    event: dict[str, Any],
    _context: object,
) -> dict[str, Any]:
    """Lambda handler for stale multipart upload reconciliation."""
    return asyncio.run(_reconcile_transfer_state(event=event))


def export_copy_worker_handler(
    event: dict[str, Any],
    _context: object,
) -> dict[str, Any]:
    """Lambda handler for queued export multipart-copy workers."""
    return asyncio.run(_export_copy_worker(event=event))


async def _validate_export(*, event: dict[str, Any]) -> dict[str, Any]:
    workflow_input = ExportWorkflowInput.model_validate(event)
    _LOGGER.info(
        "workflow_validate_export_started",
        export_id=workflow_input.export_id,
        request_id=workflow_input.request_id,
    )
    async with export_services() as services:
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
    settings = WorkflowSettings()
    async with workflow_services(settings=settings) as services:
        result = await copy_export(
            workflow_input=workflow_input,
            export_service=services.export_service,
            transfer_service=services.transfer_service,
            file_transfer_bucket=settings.file_transfer_bucket or "",
        )
    return result.model_dump(mode="json")


async def _prepare_export_copy(*, event: dict[str, Any]) -> dict[str, Any]:
    workflow_input = ExportWorkflowInput.model_validate(event)
    _LOGGER.info(
        "workflow_prepare_export_copy_started",
        export_id=workflow_input.export_id,
        request_id=workflow_input.request_id,
    )
    async with workflow_services(settings=WorkflowSettings()) as services:
        result = await prepare_export_copy(
            workflow_input=workflow_input,
            export_service=services.export_service,
            large_copy_service=services.large_copy_service,
        )
    return result.model_dump(mode="json")


async def _start_queued_export_copy(*, event: dict[str, Any]) -> dict[str, Any]:
    workflow_input = ExportWorkflowInput.model_validate(event)
    _LOGGER.info(
        "workflow_start_queued_export_copy_started",
        export_id=workflow_input.export_id,
        request_id=workflow_input.request_id,
    )
    async with workflow_services(settings=WorkflowSettings()) as services:
        result = await start_queued_export_copy(
            workflow_input=workflow_input,
            export_service=services.export_service,
            large_copy_service=services.large_copy_service,
        )
    return result.model_dump(mode="json")


async def _poll_queued_export_copy(*, event: dict[str, Any]) -> dict[str, Any]:
    workflow_input = ExportWorkflowInput.model_validate(event)
    _LOGGER.info(
        "workflow_poll_queued_export_copy_started",
        export_id=workflow_input.export_id,
        request_id=workflow_input.request_id,
    )
    async with workflow_services(settings=WorkflowSettings()) as services:
        result = await poll_queued_export_copy(
            workflow_input=workflow_input,
            export_service=services.export_service,
            large_copy_service=services.large_copy_service,
        )
    return result.model_dump(mode="json")


async def _finalize_export(*, event: dict[str, Any]) -> dict[str, Any]:
    workflow_input = ExportWorkflowInput.model_validate(event)
    _LOGGER.info(
        "workflow_finalize_export_started",
        export_id=workflow_input.export_id,
        request_id=workflow_input.request_id,
    )
    async with export_services() as services:
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
    async with export_services() as services:
        result = await fail_export(
            workflow_input=workflow_input,
            export_service=services.export_service,
        )
    return result.model_dump(mode="json")


async def _reconcile_transfer_state(*, event: dict[str, Any]) -> dict[str, Any]:
    del event
    settings = WorkflowSettings()
    session = aioboto3.Session()
    async with AsyncExitStack() as stack:
        s3_client = await stack.enter_async_context(
            session.client(
                "s3",
                config=s3_client_config(
                    use_accelerate_endpoint=(
                        settings.file_transfer_use_accelerate_endpoint
                    )
                ),
            )
        )
        dynamodb_resource = await stack.enter_async_context(
            session.resource(
                "dynamodb",
                config=aws_client_config(),
            )
        )
        upload_session_repository = build_upload_session_repository(
            table_name=settings.file_transfer_upload_sessions_table,
            dynamodb_resource=cast(
                UploadSessionDynamoResource,
                dynamodb_resource,
            ),
            enabled=True,
        )
        transfer_usage_repository = build_transfer_usage_window_repository(
            table_name=settings.file_transfer_usage_table,
            dynamodb_resource=cast(
                TransferUsageDynamoResource | None,
                dynamodb_resource,
            ),
            enabled=bool(settings.file_transfer_usage_table),
        )
        service = TransferReconciliationService(
            config=TransferReconciliationConfig(
                bucket=settings.file_transfer_bucket or "",
                upload_prefix=settings.file_transfer_upload_prefix,
                export_prefix=settings.file_transfer_export_prefix,
                stale_multipart_cleanup_age_seconds=(
                    settings.file_transfer_stale_multipart_cleanup_age_seconds
                ),
                session_scan_limit=(
                    settings.file_transfer_reconciliation_scan_limit
                ),
            ),
            s3_client=s3_client,
            upload_session_repository=upload_session_repository,
            transfer_usage_repository=transfer_usage_repository,
        )
        result = await service.reconcile()
    return result.as_dict()


async def _export_copy_worker(*, event: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    messages: list[tuple[str, ExportCopyTaskMessage]] = []
    poison_messages: list[tuple[ExportCopyPoisonMessage, int | None]] = []
    message_lag_ms: list[int | None] = []
    for record in cast(list[dict[str, Any]], event.get("Records", [])):
        message_id = str(record.get("messageId", ""))
        sent_timestamp_ms = _worker_sent_timestamp_ms(record)
        try:
            body = str(record.get("body", "{}"))
            payload = ExportCopyTaskMessage.from_dict(
                cast(dict[str, object], json.loads(body))
            )
        except Exception:
            poison = _poison_message_from_sqs_record(record)
            _LOGGER.warning(
                "workflow_export_copy_worker_message_invalid",
                message_id=message_id,
                export_id=poison.export_id if poison is not None else None,
                part_number=(
                    poison.part_number if poison is not None else None
                ),
                upload_id=poison.upload_id if poison is not None else None,
                sent_timestamp_ms=sent_timestamp_ms,
                exc_info=True,
            )
            if poison is None:
                failures.append(message_id)
            else:
                poison_messages.append((poison, sent_timestamp_ms))
            continue
        messages.append((message_id, payload))
        message_lag_ms.append(sent_timestamp_ms)
    if not messages and not poison_messages:
        return {
            "batchItemFailures": [
                {"itemIdentifier": message_id} for message_id in failures
            ]
        }
    async with workflow_services(settings=WorkflowSettings()) as services:
        for lag_ms in message_lag_ms:
            services.large_copy_service.observe_message_lag(
                sent_timestamp_ms=lag_ms
            )
        for poison, lag_ms in poison_messages:
            services.large_copy_service.observe_message_lag(
                sent_timestamp_ms=lag_ms
            )
            services.large_copy_service.record_invalid_message(
                terminalizable=True
            )
            await services.large_copy_service.terminalize_poison_message(
                poison=poison
            )
        failures.extend(
            await services.large_copy_service.process_message_batch(
                messages=messages
            )
        )
    return {
        "batchItemFailures": [
            {"itemIdentifier": message_id}
            for message_id in dict.fromkeys(failures)
        ]
    }


def _poison_message_from_sqs_record(
    record: dict[str, Any],
) -> ExportCopyPoisonMessage | None:
    message_attributes = cast(
        dict[str, Any],
        record.get("messageAttributes") or {},
    )
    export_id = _message_attribute_string(
        message_attributes,
        name="export_id",
    )
    upload_id = _message_attribute_string(
        message_attributes,
        name="upload_id",
    )
    part_number_value = _message_attribute_string(
        message_attributes,
        name="part_number",
    )
    if export_id is None or upload_id is None or part_number_value is None:
        return None
    try:
        part_number = int(part_number_value)
    except ValueError:
        return None
    if part_number < 1:
        return None
    return ExportCopyPoisonMessage(
        export_id=export_id,
        part_number=part_number,
        upload_id=upload_id,
    )


def _message_attribute_string(
    message_attributes: dict[str, Any],
    *,
    name: str,
) -> str | None:
    attribute = message_attributes.get(name)
    if not isinstance(attribute, dict):
        return None
    value = attribute.get("stringValue")
    return value if isinstance(value, str) and value.strip() else None


def _worker_sent_timestamp_ms(record: dict[str, Any]) -> int | None:
    attributes = cast(dict[str, Any], record.get("attributes") or {})
    value = attributes.get("SentTimestamp")
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed >= 0 else None
    return None
