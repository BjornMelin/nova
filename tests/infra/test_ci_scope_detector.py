from __future__ import annotations

import json

from scripts.ci import detect_workflow_scopes as scope_detector


def _outputs(changed_files: list[str]) -> dict[str, str]:
    return scope_detector._build_outputs(changed_files)


def test_runtime_changes_enable_runtime_and_conformance_lanes() -> None:
    outputs = _outputs(["packages/nova_file_api/src/nova_file_api/app.py"])

    assert outputs["run_runtime_ci"] == "true"
    assert outputs["run_conformance_required"] == "true"
    assert outputs["run_conformance_optional"] == "true"
    assert outputs["run_cfn"] == "false"
    assert outputs["docs_only"] == "false"


def test_docs_authority_changes_only_enable_cfn_lane() -> None:
    outputs = _outputs(["docs/plan/release/RELEASE-RUNBOOK.md"])

    assert outputs["run_runtime_ci"] == "false"
    assert outputs["run_conformance_required"] == "false"
    assert outputs["run_conformance_optional"] == "false"
    assert outputs["run_cfn"] == "true"
    assert outputs["docs_only"] == "true"


def test_docs_history_changes_remain_docs_only_without_required_lanes() -> None:
    outputs = _outputs(["docs/history/2026-02-cutover/notes.md"])

    assert outputs["run_runtime_ci"] == "false"
    assert outputs["run_conformance_required"] == "false"
    assert outputs["run_conformance_optional"] == "false"
    assert outputs["run_cfn"] == "false"
    assert outputs["docs_only"] == "true"


def test_workflow_changes_mark_cfn_and_targeted_ci_lanes() -> None:
    outputs = _outputs([".github/workflows/ci.yml"])

    assert outputs["run_runtime_ci"] == "true"
    assert outputs["run_conformance_required"] == "false"
    assert outputs["run_conformance_optional"] == "false"
    assert outputs["run_cfn"] == "true"
    affected_units = json.loads(outputs["affected_units_json"])
    assert affected_units == []
