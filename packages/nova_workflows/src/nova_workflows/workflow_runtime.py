"""Runtime assembly helpers for workflow task handlers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import cast

import aioboto3

from nova_file_api.workflow_facade import (
    DynamoExportRepository,
    DynamoResource,
    ExportCopyPartsDynamoResource,
    LargeExportCopyCoordinator,
    S3ExportTransferService,
    WorkflowExportStateService,
    aws_client_config,
    build_export_copy_part_repository,
    s3_client_config,
)
from nova_runtime_support.metrics import MetricsCollector
from nova_workflows.workflow_config import (
    WorkflowSettings,
    export_transfer_config_from_settings,
)


@dataclass(slots=True)
class WorkflowServices:
    """Materialized services required by workflow tasks."""

    export_service: WorkflowExportStateService
    transfer_service: S3ExportTransferService
    large_copy_service: LargeExportCopyCoordinator


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
    return WorkflowExportStateService(
        repository=repository,
        metrics=MetricsCollector(namespace=resolved_settings.metrics_namespace),
    )


@asynccontextmanager
async def export_services(
    *,
    settings: WorkflowSettings | None = None,
) -> AsyncIterator[ExportServices]:
    """Build the export service without the S3 transfer dependency."""
    resolved_settings = WorkflowSettings() if settings is None else settings
    session = aioboto3.Session()
    async with AsyncExitStack() as stack:
        dynamodb_resource = await stack.enter_async_context(
            session.resource(
                "dynamodb",
                config=aws_client_config(),
            )
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
    export_copy_parts_table = (
        resolved_settings.file_transfer_export_copy_parts_table or ""
    ).strip()
    export_copy_queue_url = (
        resolved_settings.file_transfer_export_copy_queue_url or ""
    ).strip()
    if resolved_settings.exports_enabled and (
        not export_copy_parts_table or not export_copy_queue_url
    ):
        raise ValueError(
            "FILE_TRANSFER_EXPORT_COPY_PARTS_TABLE and "
            "FILE_TRANSFER_EXPORT_COPY_QUEUE_URL must be configured when "
            "EXPORTS_ENABLED=true"
        )
    session = aioboto3.Session()
    async with AsyncExitStack() as stack:
        s3_client = await stack.enter_async_context(
            session.client(
                "s3",
                config=s3_client_config(
                    use_accelerate_endpoint=(
                        resolved_settings.file_transfer_use_accelerate_endpoint
                    )
                ),
            )
        )
        sqs_client = await stack.enter_async_context(
            session.client(
                "sqs",
                config=aws_client_config(),
            )
        )
        dynamodb_resource = await stack.enter_async_context(
            session.resource(
                "dynamodb",
                config=aws_client_config(),
            )
        )
        export_service = _build_export_service(
            resolved_settings=resolved_settings,
            dynamodb_resource=dynamodb_resource,
        )
        export_transfer_cfg = export_transfer_config_from_settings(
            resolved_settings
        )
        transfer_service = S3ExportTransferService(
            config=export_transfer_cfg,
            s3_client=s3_client,
        )
        large_copy_service = LargeExportCopyCoordinator(
            bucket=export_transfer_cfg.bucket,
            upload_prefix=resolved_settings.file_transfer_upload_prefix,
            export_prefix=resolved_settings.file_transfer_export_prefix,
            copy_part_size_bytes=(
                resolved_settings.file_transfer_export_copy_part_size_bytes
            ),
            worker_threshold_bytes=(
                resolved_settings.file_transfer_large_export_worker_threshold_bytes
            ),
            max_attempts=(
                resolved_settings.file_transfer_export_copy_worker_attempts
            ),
            queue_url=export_copy_queue_url,
            s3_client=s3_client,
            sqs_client=sqs_client,
            export_repository=export_service.repository,
            export_copy_part_repository=build_export_copy_part_repository(
                table_name=export_copy_parts_table,
                dynamodb_resource=cast(
                    ExportCopyPartsDynamoResource | None,
                    dynamodb_resource,
                ),
                enabled=bool(export_copy_parts_table),
                claim_lease_seconds=(
                    resolved_settings.file_transfer_export_copy_worker_lease_seconds
                ),
            ),
            metrics=export_service.metrics,
        )
        yield WorkflowServices(
            export_service=export_service,
            transfer_service=transfer_service,
            large_copy_service=large_copy_service,
        )
