"""Tests for shared workflow runtime settings and service assembly."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from botocore.config import Config
from pydantic import ValidationError

from nova_file_api.export_models import ExportRecord, ExportStatus
from nova_file_api.workflow_facade import (
    DynamoExportRepository,
    MemoryExportRepository,
    NoopExportMetrics,
    WorkflowExportStateService,
    update_export_status_shared,
)
from nova_runtime_support.metrics import MetricsCollector
from nova_workflows.workflow_config import (
    WorkflowSettings,
    export_transfer_config_from_settings,
)
from nova_workflows.workflow_runtime import (
    _build_export_service,
    workflow_services,
)


class _AsyncContextValue:
    def __init__(self, value: object) -> None:
        self._value = value

    async def __aenter__(self) -> object:
        return self._value

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> bool:
        del exc_type, exc, tb
        return False


class _RecordingSession:
    def __init__(self) -> None:
        self.client_calls: list[tuple[str, Config | None]] = []
        self.resource_calls: list[tuple[str, Config | None]] = []

    def client(
        self, service_name: str, *, config: Config | None = None
    ) -> _AsyncContextValue:
        self.client_calls.append((service_name, config))
        return _AsyncContextValue(object())

    def resource(
        self, service_name: str, *, config: Config | None = None
    ) -> _AsyncContextValue:
        self.resource_calls.append((service_name, config))
        return _AsyncContextValue(object())


def test_workflow_settings_require_exports_table_when_exports_enabled() -> None:
    """Exports-enabled workflow settings must require a DynamoDB table."""
    with pytest.raises(ValidationError, match="EXPORTS_DYNAMODB_TABLE"):
        WorkflowSettings.model_validate({"EXPORTS_ENABLED": True})


def test_workflow_settings_require_copy_backends_when_exports_enabled() -> None:
    """Require copy queue and parts table when exports are enabled."""
    with pytest.raises(ValidationError, match="FILE_TRANSFER_EXPORT_COPY"):
        WorkflowSettings.model_validate(
            {
                "EXPORTS_ENABLED": True,
                "EXPORTS_DYNAMODB_TABLE": "exports-table",
            }
        )


def test_workflow_settings_allow_missing_exports_table_when_disabled() -> None:
    """Exports-disabled workflow settings may omit the DynamoDB table."""
    settings = WorkflowSettings.model_validate({"EXPORTS_ENABLED": False})

    assert settings.exports_enabled is False
    assert settings.exports_dynamodb_table is None


def test_workflow_settings_require_export_copy_worker_backends_together() -> (
    None
):
    """Copy-parts table and worker queue must be configured together."""
    with pytest.raises(
        ValidationError,
        match="FILE_TRANSFER_EXPORT_COPY_PARTS_TABLE",
    ):
        WorkflowSettings.model_validate(
            {
                "EXPORTS_ENABLED": False,
                "FILE_TRANSFER_EXPORT_COPY_PARTS_TABLE": "parts-table",
            }
        )


def test_workflow_settings_require_export_copy_worker_queue_with_table() -> (
    None
):
    """Worker queue without copy-parts table must be rejected."""
    with pytest.raises(
        ValidationError,
        match="FILE_TRANSFER_EXPORT_COPY_QUEUE_URL",
    ):
        WorkflowSettings.model_validate(
            {
                "EXPORTS_ENABLED": False,
                "FILE_TRANSFER_EXPORT_COPY_QUEUE_URL": (
                    "https://sqs.us-west-2.amazonaws.com/123/queue"
                ),
            }
        )


def test_build_export_service_uses_dynamo_repository() -> None:
    """Workflow runtime assembly should always build a Dynamo repository."""
    service = _build_export_service(
        resolved_settings=WorkflowSettings.model_validate(
            {
                "EXPORTS_ENABLED": True,
                "EXPORTS_DYNAMODB_TABLE": "exports-table",
                "FILE_TRANSFER_EXPORT_COPY_QUEUE_URL": (
                    "https://sqs.us-west-2.amazonaws.com/123456789012/q"
                ),
                "FILE_TRANSFER_EXPORT_COPY_PARTS_TABLE": "export-copy-parts",
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
        file_transfer_bucket=None,
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


@pytest.mark.anyio
async def test_workflow_services_reject_blank_copy_worker_settings() -> None:
    """Workflow assembly must fail closed on blank queued-copy settings."""
    settings = WorkflowSettings.model_construct(
        exports_enabled=True,
        exports_dynamodb_table="exports-table",
        file_transfer_bucket="bucket",
        file_transfer_upload_prefix="uploads/",
        file_transfer_export_prefix="exports/",
        file_transfer_tmp_prefix="tmp/",
        file_transfer_part_size_bytes=128 * 1024 * 1024,
        file_transfer_max_concurrency=4,
        file_transfer_use_accelerate_endpoint=False,
        file_transfer_export_copy_queue_url="   ",
        file_transfer_export_copy_parts_table="export-copy-parts",
    )

    with pytest.raises(ValueError, match="FILE_TRANSFER_EXPORT_COPY"):
        async with workflow_services(settings=settings):
            pytest.fail("workflow_services should not yield")


@pytest.mark.anyio
async def test_workflow_services_use_shared_aws_client_configs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import nova_workflows.workflow_runtime as workflow_runtime_module

    session = _RecordingSession()
    monkeypatch.setattr(
        workflow_runtime_module.aioboto3,
        "Session",
        lambda: session,
    )

    async with workflow_services(
        settings=WorkflowSettings.model_validate(
            {
                "EXPORTS_ENABLED": True,
                "EXPORTS_DYNAMODB_TABLE": "exports-table",
                "FILE_TRANSFER_BUCKET": "workflow-bucket",
                "FILE_TRANSFER_USE_ACCELERATE_ENDPOINT": True,
                "FILE_TRANSFER_EXPORT_COPY_QUEUE_URL": (
                    "https://sqs.us-west-2.amazonaws.com/123456789012/q"
                ),
                "FILE_TRANSFER_EXPORT_COPY_PARTS_TABLE": ("export-copy-parts"),
            }
        )
    ) as services:
        assert services.transfer_service is not None

    assert [name for name, _ in session.client_calls] == ["s3", "sqs"]
    assert [name for name, _ in session.resource_calls] == ["dynamodb"]
    assert isinstance(session.client_calls[0][1], Config)
    assert session.client_calls[0][1].s3 == {"use_accelerate_endpoint": True}
    assert isinstance(session.client_calls[1][1], Config)
    assert session.client_calls[1][1].s3 is None
    assert isinstance(session.resource_calls[0][1], Config)


def test_export_transfer_config_strips_bucket() -> None:
    settings = WorkflowSettings.model_validate(
        {
            "EXPORTS_ENABLED": False,
            "FILE_TRANSFER_BUCKET": "  workflow-bucket  ",
        }
    )

    config = export_transfer_config_from_settings(settings)

    assert config.bucket == "workflow-bucket"
    assert config.part_size_bytes == 128 * 1024 * 1024
    assert config.copy_part_size_bytes == 2 * 1024 * 1024 * 1024
    assert config.max_concurrency == 8


def test_export_transfer_config_uses_dedicated_copy_tuning() -> None:
    settings = WorkflowSettings.model_validate(
        {
            "EXPORTS_ENABLED": False,
            "FILE_TRANSFER_BUCKET": "workflow-bucket",
            "FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES": 1_073_741_824,
            "FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY": 5,
        }
    )

    config = export_transfer_config_from_settings(settings)

    assert config.part_size_bytes == 128 * 1024 * 1024
    assert config.copy_part_size_bytes == 1_073_741_824
    assert config.max_concurrency == 5


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


@pytest.mark.anyio
@pytest.mark.parametrize(
    "initial_status,target_status,metric_key,error",
    [
        (
            ExportStatus.QUEUED,
            ExportStatus.VALIDATING,
            "exports_queued_age_ms",
            None,
        ),
        (
            ExportStatus.COPYING,
            ExportStatus.FINALIZING,
            "exports_copying_age_ms",
            None,
        ),
        (
            ExportStatus.FINALIZING,
            ExportStatus.FAILED,
            "exports_finalizing_age_ms",
            "boom",
        ),
    ],
)
async def test_update_export_status_shared_records_stage_age_metric(
    initial_status: ExportStatus,
    target_status: ExportStatus,
    metric_key: str,
    error: str | None,
) -> None:
    repository = MemoryExportRepository()
    metrics = MetricsCollector(namespace="Tests")
    now = datetime.now(tz=UTC)
    started = now - timedelta(minutes=1)
    await repository.create(
        ExportRecord(
            export_id="export-1",
            scope_id="scope-1",
            request_id="req-1",
            source_key="uploads/scope-1/source.csv",
            filename="source.csv",
            status=initial_status,
            output=None,
            error=None,
            created_at=started,
            updated_at=started,
        )
    )

    await update_export_status_shared(
        repository=repository,
        metrics=metrics,
        export_id="export-1",
        status=target_status,
        error=error,
    )

    latencies = metrics.latency_snapshot()
    assert latencies[metric_key] > 0


@pytest.mark.anyio
async def test_update_export_status_shared_keeps_stage_age_on_same_status_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = MemoryExportRepository()
    metrics = MetricsCollector(namespace="Tests")
    started = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
    validating_time = started + timedelta(minutes=1)
    copying_time = started + timedelta(minutes=2)
    retry_time = started + timedelta(minutes=3)
    finalize_time = started + timedelta(minutes=5)
    now_values = iter(
        [validating_time, copying_time, retry_time, finalize_time]
    )
    monkeypatch.setattr(
        "nova_file_api.export_runtime._utc_now",
        lambda: next(now_values),
    )
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
            created_at=started,
            updated_at=started,
        )
    )

    await update_export_status_shared(
        repository=repository,
        metrics=metrics,
        export_id="export-1",
        status=ExportStatus.VALIDATING,
    )

    copied = await update_export_status_shared(
        repository=repository,
        metrics=metrics,
        export_id="export-1",
        status=ExportStatus.COPYING,
    )
    assert copied.updated_at == copying_time

    retried = await update_export_status_shared(
        repository=repository,
        metrics=metrics,
        export_id="export-1",
        status=ExportStatus.COPYING,
    )
    assert retried.updated_at == copying_time

    await update_export_status_shared(
        repository=repository,
        metrics=metrics,
        export_id="export-1",
        status=ExportStatus.FINALIZING,
    )

    latencies = metrics.latency_snapshot()
    assert latencies["exports_queued_age_ms"] == 60000.0
    assert latencies["exports_copying_age_ms"] == 180000.0
