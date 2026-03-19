"""Tests for the CI workflow scope detector script and output contract."""

from __future__ import annotations

import json
import operator
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from .helpers import REPO_ROOT, load_repo_module

scope_detector = cast(
    object,
    load_repo_module(
        "tests.infra.detect_workflow_scopes",
        "scripts/ci/detect_workflow_scopes.py",
    ),
)
scope_detector_build_outputs = cast(
    Callable[[list[str]], dict[str, str]],
    operator.attrgetter("_build_outputs")(scope_detector),
)


def _outputs(changed_files: list[str]) -> dict[str, str]:
    return scope_detector_build_outputs(changed_files)


def _write_repo_file(
    temp_repo: Path,
    rel_path: str,
    *,
    content: str | None = None,
) -> None:
    target = temp_repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if content is None:
        content = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    _ = target.write_text(content, encoding="utf-8")


def _run_git(git_executable: str, repo_root: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603
        [git_executable, *args],
        check=True,
        cwd=repo_root,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_runtime_changes_enable_runtime_and_conformance_lanes() -> None:
    """Runtime edits should enable runtime and full conformance lanes only."""
    outputs = _outputs(["packages/nova_file_api/src/nova_file_api/app.py"])

    assert outputs["run_runtime_ci"] == "true"
    assert outputs["run_conformance_required"] == "true"
    assert outputs["run_conformance_optional"] == "true"
    assert outputs["run_cfn"] == "false"
    assert outputs["docs_only"] == "false"


def test_docs_authority_changes_only_enable_cfn_lane() -> None:
    """Docs authority edits should route to CFN lane only."""
    outputs = _outputs(["docs/plan/release/RELEASE-RUNBOOK.md"])

    assert outputs["run_runtime_ci"] == "false"
    assert outputs["run_conformance_required"] == "false"
    assert outputs["run_conformance_optional"] == "false"
    assert outputs["run_cfn"] == "true"
    assert outputs["docs_only"] == "true"


def test_prd_changes_enable_only_cfn_lane() -> None:
    """PRD changes should map only to CFN validation."""
    outputs = _outputs(["docs/PRD.md"])

    assert outputs["run_runtime_ci"] == "false"
    assert outputs["run_conformance_required"] == "false"
    assert outputs["run_conformance_optional"] == "false"
    assert outputs["run_cfn"] == "true"
    assert outputs["docs_only"] == "true"


def test_docs_history_changes_remain_docs_only_without_required_lanes() -> None:
    """Docs history changes should stay docs-only with no required CI lanes."""
    outputs = _outputs(["docs/history/2026-02-cutover/notes.md"])

    assert outputs["run_runtime_ci"] == "false"
    assert outputs["run_conformance_required"] == "false"
    assert outputs["run_conformance_optional"] == "false"
    assert outputs["run_cfn"] == "false"
    assert outputs["docs_only"] == "true"


def test_workflow_changes_mark_cfn_and_targeted_ci_lanes() -> None:
    """CI workflow changes should trigger runtime and CFN lanes."""
    outputs = _outputs([".github/workflows/ci.yml"])

    assert outputs["run_runtime_ci"] == "true"
    assert outputs["run_conformance_required"] == "false"
    assert outputs["run_conformance_optional"] == "false"
    assert outputs["run_cfn"] == "true"
    affected_units = cast(list[str], json.loads(outputs["affected_units_json"]))
    assert affected_units == []


@pytest.mark.parametrize(
    "path",
    [
        "scripts/release/generate_clients.py",
        "scripts/release/generate_python_clients.py",
    ],
)
def test_generator_entrypoints_enable_conformance_and_cfn_lanes(
    path: str,
) -> None:
    """Generator entrypoints should enable conformance and CFN lanes."""
    outputs = _outputs([path])

    assert outputs["run_runtime_ci"] == "false"
    assert outputs["run_conformance_required"] == "true"
    assert outputs["run_conformance_optional"] == "true"
    assert outputs["run_cfn"] == "true"
    assert outputs["docs_only"] == "false"


def test_scope_detector_cli_emits_expected_output_contract(
    tmp_path: Path,
) -> None:
    """CLI contract should emit classifier outputs deterministically."""
    git_executable = shutil.which("git")
    assert git_executable, "git executable is required for CLI contract tests"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_repo_file(
        repo_root,
        "pyproject.toml",
        content="[tool.uv.workspace]\nmembers = []\n",
    )
    _write_repo_file(repo_root, "scripts/ci/detect_workflow_scopes.py")
    _write_repo_file(repo_root, "scripts/release/common.py")
    _ = _run_git(git_executable, repo_root, "init")
    _ = _run_git(git_executable, repo_root, "config", "user.name", "Nova Tests")
    _ = _run_git(
        git_executable,
        repo_root,
        "config",
        "user.email",
        "nova-tests@example.com",
    )
    _ = _run_git(git_executable, repo_root, "add", ".")
    _ = _run_git(git_executable, repo_root, "commit", "-m", "initial")
    head_sha = _run_git(git_executable, repo_root, "rev-parse", "HEAD")
    output_path = tmp_path / "github-output.txt"

    _ = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "scripts/ci/detect_workflow_scopes.py",
            "--event-name",
            "pull_request",
            "--head-sha",
            head_sha,
            "--base-sha",
            head_sha,
            "--github-output",
            str(output_path),
        ],
        check=True,
        cwd=repo_root,
    )

    output_lines = output_path.read_text(encoding="utf-8").splitlines()
    outputs = dict(line.split("=", 1) for line in output_lines if "=" in line)

    assert outputs["changed_files_json"] == "[]"
    assert json.loads(outputs["affected_units_json"]) == []
    assert outputs["docs_only"] == "false"
    assert outputs["run_runtime_ci"] == "false"
    assert outputs["run_conformance_required"] == "false"
    assert outputs["run_conformance_optional"] == "false"
    assert outputs["run_cfn"] == "false"
