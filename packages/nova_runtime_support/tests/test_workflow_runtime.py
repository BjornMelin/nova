"""Tests for shared workflow runtime settings and service assembly."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nova_runtime_support.export_runtime import (
    DynamoExportRepository,
    WorkflowExportStateService,
)
from nova_runtime_support.workflow_config import WorkflowSettings
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
            }
        ),
        dynamodb_resource=object(),
    )

    assert isinstance(service, WorkflowExportStateService)
    assert isinstance(service.repository, DynamoExportRepository)


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
