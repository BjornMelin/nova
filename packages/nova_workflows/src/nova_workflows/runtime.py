"""Runtime assembly helpers for workflow task handlers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from botocore.config import Config
from nova_file_api.aws import new_aioboto3_session
from nova_file_api.config import Settings
from nova_file_api.dependencies import (
    build_export_repository,
    build_export_service,
    build_metrics,
    build_transfer_service,
)
from nova_file_api.exports import ExportService, MemoryExportPublisher
from nova_file_api.transfer import TransferService


@dataclass(slots=True)
class WorkflowServices:
    """Materialized services required by workflow tasks."""

    export_service: ExportService
    transfer_service: TransferService


@asynccontextmanager
async def workflow_services(
    *,
    settings: Settings | None = None,
) -> AsyncIterator[WorkflowServices]:
    """Build workflow task services from the current environment."""
    resolved_settings = Settings() if settings is None else settings
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
        metrics = build_metrics(settings=resolved_settings)
        repository = build_export_repository(
            settings=resolved_settings,
            dynamodb_resource=dynamodb_resource,
        )
        export_service = build_export_service(
            export_repository=repository,
            export_publisher=MemoryExportPublisher(process_immediately=False),
            metrics=metrics,
        )
        transfer_service = build_transfer_service(
            settings=resolved_settings,
            s3_client=s3_client,
        )
        yield WorkflowServices(
            export_service=export_service,
            transfer_service=transfer_service,
        )
