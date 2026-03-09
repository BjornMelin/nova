from __future__ import annotations

from pathlib import Path

import pytest

from scripts.release.generate_clients import (
    Operation,
    _assert_unique_operation_ids,
    _default_operation_id,
)


def test_default_operation_id_keeps_path_parameter_names() -> None:
    assert (
        _default_operation_id(
            method="get",
            path="/v1/jobs/{job_id}/events",
        )
        == "get_v1_jobs_by_job_id_events"
    )


def test_assert_unique_operation_ids_fails_on_collision() -> None:
    with pytest.raises(ValueError, match="Duplicate operationId"):
        _assert_unique_operation_ids(
            spec_path=Path("spec.json"),
            operations=[
                Operation(
                    operation_id="job_lookup",
                    method="GET",
                    path="/v1/jobs/{job_id}",
                    summary=None,
                ),
                Operation(
                    operation_id="job_lookup",
                    method="GET",
                    path="/v1/jobs/{other_id}",
                    summary=None,
                ),
            ],
        )
