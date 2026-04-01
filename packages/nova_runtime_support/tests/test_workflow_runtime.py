"""Tests for shared workflow runtime settings and service assembly."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from nova_runtime_support.export_models import ExportRecord, ExportStatus
from nova_runtime_support.export_runtime import (
    DynamoExportRepository,
    MemoryExportRepository,
    NoopExportMetrics,
    WorkflowExportStateService,
    update_export_status_shared,
)
from nova_runtime_support.metrics import MetricsCollector
from nova_runtime_support.workflow_config import (
    WorkflowSettings,
    export_transfer_config_from_settings,
)
from nova_runtime_support.workflow_runtime import _build_export_service


def test_workflow_settings_require_exports_table_when_exports_enabled() -> None:
    """Exports-enabled workflow settings must require a DynamoDB table."""
    with pytest.raises(ValidationError, match="EXPORTS_DYNAMODB_TABLE"):
        WorkflowSettings.model_validate({"EXPORTS_ENABLED": True})


def test_workflow_settings_allow_missing_exports_table_when_disabled() -> None:
    """Exports-disabled workflow settings may omit the DynamoDB table."""
    settings = WorkflowSettings.model_validate({"EXPORTS_ENABLED": False})

    assert settings.exports_enabled is False
    assert settings.exports_dynamodb_table is None


def test_build_export_service_uses_dynamo_repository() -> None:
    """Workflow runtime assembly should always build a Dynamo repository."""
    service = _build_export_service(
        resolved_settings=WorkflowSettings.model_validate(
            {
                "EXPORTS_ENABLED": True,
                "EXPORTS_DYNAMODB_TABLE": "exports-table",
                "METRICS_NAMESPACE": "WorkflowTests",
            }
        ),
        dynamodb_resource=object(),
    )

    assert isinstance(service, WorkflowExportStateService)
    assert isinstance(service.repository, DynamoExportRepository)
    assert isinstance(service.metrics, MetricsCollector)
    assert not isinstance(service.metrics, NoopExportMetrics)
    assert service.metrics._namespace == "WorkflowTests"


def test_build_export_service_rejects_blank_exports_table() -> None:
    """Workflow runtime assembly must fail closed on a blank exports table."""
    settings = WorkflowSettings.model_construct(
        exports_enabled=True,
        exports_dynamodb_table="  ",
        file_transfer_bucket="",
        file_transfer_upload_prefix="uploads/",
        file_transfer_export_prefix="exports/",
        file_transfer_tmp_prefix="tmp/",
        file_transfer_part_size_bytes=128 * 1024 * 1024,
        file_transfer_max_concurrency=4,
        file_transfer_use_accelerate_endpoint=False,
    )

    with pytest.raises(ValueError, match="EXPORTS_DYNAMODB_TABLE"):
        _build_export_service(
            resolved_settings=settings,
            dynamodb_resource=object(),
        )


def test_export_transfer_config_strips_bucket() -> None:
    settings = WorkflowSettings.model_validate(
        {
            "EXPORTS_ENABLED": False,
            "FILE_TRANSFER_BUCKET": "  workflow-bucket  ",
        }
    )

    config = export_transfer_config_from_settings(settings)

    assert config.bucket == "workflow-bucket"


def test_export_transfer_config_rejects_blank_bucket() -> None:
    settings = WorkflowSettings.model_validate(
        {
            "EXPORTS_ENABLED": False,
            "FILE_TRANSFER_BUCKET": "   ",
        }
    )

    with pytest.raises(ValueError, match="FILE_TRANSFER_BUCKET"):
        export_transfer_config_from_settings(settings)


@pytest.mark.anyio
async def test_update_export_status_shared_preserves_terminal_metrics() -> None:
    repository = MemoryExportRepository()
    metrics = MetricsCollector(namespace="Tests")
    now = datetime.now(tz=UTC)
    await repository.create(
        ExportRecord(
            export_id="export-1",
            scope_id="scope-1",
            request_id="req-1",
            source_key="uploads/scope-1/source.csv",
            filename="source.csv",
            status=ExportStatus.QUEUED,
            output=None,
            error=None,
            created_at=now,
            updated_at=now,
        )
    )

    updated = await update_export_status_shared(
        repository=repository,
        metrics=metrics,
        export_id="export-1",
        status=ExportStatus.FAILED,
    )

    assert updated.error == "export_failed"
    assert metrics.counters_snapshot()["exports_failed"] == 1
    assert metrics.counters_snapshot()["exports_status_updates_total"] == 1


@pytest.mark.anyio
async def test_update_export_status_shared_requires_output_for_success() -> (
    None
):
    repository = MemoryExportRepository()
    now = datetime.now(tz=UTC)
    await repository.create(
        ExportRecord(
            export_id="export-1",
            scope_id="scope-1",
            request_id="req-1",
            source_key="uploads/scope-1/source.csv",
            filename="source.csv",
            status=ExportStatus.FINALIZING,
            output=None,
            error=None,
            created_at=now,
            updated_at=now,
        )
    )

    with pytest.raises(ValueError, match="export output is required"):
        await update_export_status_shared(
            repository=repository,
            metrics=NoopExportMetrics(),
            export_id="export-1",
            status=ExportStatus.SUCCEEDED,
        )
