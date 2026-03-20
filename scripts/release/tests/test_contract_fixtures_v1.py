"""Contract fixture validation for canonical v1 fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from nova_file_api.models import (
    CapabilitiesResponse,
    EnqueueJobRequest,
    EnqueueJobResponse,
    ErrorEnvelope,
    InitiateUploadRequest,
    InitiateUploadResponse,
    JobStatusResponse,
    ReleaseInfoResponse,
    ResourcePlanResponse,
)

from scripts.conformance.validate_lane import validate_lane

FIXTURE_ROOT = Path("packages/contracts/fixtures/v1")


def _read_json(relative_path: str) -> dict[str, Any]:
    payload = json.loads(
        (FIXTURE_ROOT / relative_path).read_text(encoding="utf-8")
    )
    assert isinstance(payload, dict)
    return payload


def test_manifest_paths_exist() -> None:
    manifest = _read_json("manifest.json")

    for group in ("schemas", "fixtures"):
        assert group in manifest

    for schema_path in manifest["schemas"].values():
        assert (FIXTURE_ROOT / schema_path).is_file()

    for domain in manifest["fixtures"].values():
        for fixture_path in domain.values():
            assert (FIXTURE_ROOT / fixture_path).is_file()


def test_transfer_and_jobs_fixtures_match_contract_models() -> None:
    InitiateUploadRequest.model_validate(
        _read_json("fixtures/transfer/initiate.request.json")
    )
    InitiateUploadResponse.model_validate(
        _read_json("fixtures/transfer/initiate.success.json")
    )

    EnqueueJobRequest.model_validate(
        _read_json("fixtures/jobs/enqueue.request.json")
    )
    EnqueueJobResponse.model_validate(
        _read_json("fixtures/jobs/enqueue.success.json")
    )
    JobStatusResponse.model_validate(
        _read_json("fixtures/jobs/status.success.json")
    )

    queue_error = _read_json("fixtures/jobs/enqueue.503.queue-unavailable.json")
    ErrorEnvelope.model_validate(queue_error)


def test_v1_api_fixtures_match_contract_models() -> None:
    CapabilitiesResponse.model_validate(
        _read_json("fixtures/v1api/capabilities.success.json")
    )
    ResourcePlanResponse.model_validate(
        _read_json("fixtures/v1api/resources.plan.success.json")
    )
    ReleaseInfoResponse.model_validate(
        _read_json("fixtures/v1api/releases.info.success.json")
    )


@pytest.mark.parametrize("lane", ["dash", "shiny", "typescript"])
def test_validate_lane_contract(lane: str) -> None:
    validate_lane(lane)
