"""Runtime assembly helpers for workflow task handlers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import cast

from botocore.config import Config

from nova_runtime_support.aws import new_aioboto3_session
from nova_runtime_support.export_runtime import (
    DynamoExportRepository,
    DynamoResource,
    WorkflowExportStateService,
)
from nova_runtime_support.export_transfer import S3ExportTransferService
from nova_runtime_support.workflow_config import (
    WorkflowSettings,
    export_transfer_config_from_settings,
)


@dataclass(slots=True)
class WorkflowServices:
    """Materialized services required by workflow tasks."""

    export_service: WorkflowExportStateService
    transfer_service: S3ExportTransferService


@dataclass(slots=True)
class ExportServices:
    """Materialized export service used by workflow validation handlers."""

    export_service: WorkflowExportStateService


def _build_export_service(
    *,
    resolved_settings: WorkflowSettings,
    dynamodb_resource: object,
) -> WorkflowExportStateService:
    table_name = (resolved_settings.exports_dynamodb_table or "").strip()
    if not table_name:
        raise ValueError(
            "EXPORTS_DYNAMODB_TABLE must be configured when "
            "EXPORTS_ENABLED=true"
        )
    repository = DynamoExportRepository(
        table_name=table_name,
        dynamodb_resource=cast(DynamoResource, dynamodb_resource),
    )
    return WorkflowExportStateService(repository=repository)


@asynccontextmanager
async def export_services(
    *,
    settings: WorkflowSettings | None = None,
) -> AsyncIterator[ExportServices]:
    """Build the export service without the S3 transfer dependency."""
    resolved_settings = WorkflowSettings() if settings is None else settings
    session = new_aioboto3_session()
    async with AsyncExitStack() as stack:
        dynamodb_resource = await stack.enter_async_context(
            session.resource("dynamodb")
        )
        export_service = _build_export_service(
            resolved_settings=resolved_settings,
            dynamodb_resource=dynamodb_resource,
        )
        yield ExportServices(export_service=export_service)


@asynccontextmanager
async def workflow_services(
    *,
    settings: WorkflowSettings | None = None,
) -> AsyncIterator[WorkflowServices]:
    """Build workflow task services from the current environment."""
    resolved_settings = WorkflowSettings() if settings is None else settings
    session = new_aioboto3_session()
    s3_config = Config(
        s3={
            "use_accelerate_endpoint": (
                resolved_settings.file_transfer_use_accelerate_endpoint
            )
        }
    )
    async with AsyncExitStack() as stack:
        s3_client = await stack.enter_async_context(
            session.client("s3", config=s3_config)
        )
        dynamodb_resource = await stack.enter_async_context(
            session.resource("dynamodb")
        )
        export_service = _build_export_service(
            resolved_settings=resolved_settings,
            dynamodb_resource=dynamodb_resource,
        )
        transfer_service = S3ExportTransferService(
            config=export_transfer_config_from_settings(resolved_settings),
            s3_client=s3_client,
        )
        yield WorkflowServices(
            export_service=export_service,
            transfer_service=transfer_service,
        )
