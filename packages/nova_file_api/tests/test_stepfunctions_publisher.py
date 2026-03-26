from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from nova_file_api.config import Settings
from nova_file_api.dependencies import build_export_publisher
from nova_file_api.exports import StepFunctionsExportPublisher
from nova_file_api.models import ExportRecord, ExportStatus, JobsQueueBackend


class _FakeStepFunctionsClient:
    def __init__(self) -> None:
        self.start_calls: list[dict[str, Any]] = []

    async def start_execution(self, **kwargs: object) -> dict[str, object]:
        self.start_calls.append(dict(kwargs))
        return {"executionArn": "arn:aws:states:::execution:test"}

    async def describe_state_machine(
        self, **kwargs: object
    ) -> dict[str, object]:
        return {"stateMachineArn": kwargs["stateMachineArn"]}


@pytest.mark.anyio
async def test_build_export_publisher_supports_step_functions_backend() -> None:
    settings = Settings.model_validate(
        {
            "IDEMPOTENCY_DYNAMODB_TABLE": "idempotency-table",
            "JOBS_ENABLED": True,
            "JOBS_QUEUE_BACKEND": JobsQueueBackend.STEP_FUNCTIONS,
            "JOBS_STEP_FUNCTIONS_STATE_MACHINE_ARN": (
                "arn:aws:states:us-east-1:123456789012:stateMachine:nova"
            ),
        }
    )
    fake_client = _FakeStepFunctionsClient()

    publisher = build_export_publisher(
        settings=settings,
        sqs_client=None,
        stepfunctions_client=fake_client,
    )

    assert isinstance(publisher, StepFunctionsExportPublisher)


@pytest.mark.anyio
async def test_step_functions_publisher_starts_execution() -> None:
    publisher = StepFunctionsExportPublisher(
        state_machine_arn=(
            "arn:aws:states:us-east-1:123456789012:stateMachine:nova"
        ),
        stepfunctions_client=_FakeStepFunctionsClient(),
    )
    now = datetime.now(tz=UTC)
    record = ExportRecord(
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

    await publisher.publish(export=record)
    client = publisher.stepfunctions_client
    assert isinstance(client, _FakeStepFunctionsClient)
    assert client.start_calls
    start_call = client.start_calls[0]
    payload = json.loads(start_call["input"])
    assert start_call["name"] == "export-1"
    assert start_call["stateMachineArn"] == publisher.state_machine_arn
    assert payload["export_id"] == "export-1"
    assert payload["scope_id"] == "scope-1"
    assert payload["source_key"] == "uploads/scope-1/source.csv"
    assert payload["filename"] == "source.csv"
    assert payload["request_id"] == "req-1"
    assert payload["status"] == ExportStatus.QUEUED.value
    assert payload["created_at"] == now.isoformat()
    assert payload["updated_at"] == now.isoformat()
