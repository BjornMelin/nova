"""Tests for release preparation preflight behavior."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

prepare_release_pr = importlib.import_module(
    "scripts.release.prepare_release_pr"
)


def test_main_preflights_uv_before_version_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_release_pr.py",
            "--repo-root",
            str(tmp_path),
        ],
    )
    monkeypatch.setattr(
        "scripts.release.prepare_release_pr.common.load_workspace_units",
        lambda repo_root: {},
    )
    monkeypatch.setattr(
        "scripts.release.prepare_release_pr.common.run_git",
        lambda repo_root, args: "abc123",
    )
    monkeypatch.setattr(
        "scripts.release.prepare_release_pr.common.find_manifest_base_commit",
        lambda repo_root, manifest_path: None,
    )
    monkeypatch.setattr(
        "scripts.release.prepare_release_pr.common.list_changed_files",
        lambda repo_root, head_commit, base_commit: [],
    )
    monkeypatch.setattr(
        "scripts.release.prepare_release_pr.changed_units.build_changed_units_report",
        lambda **kwargs: {"changed_units": []},
    )
    monkeypatch.setattr(
        "scripts.release.prepare_release_pr.common.collect_commit_messages",
        lambda repo_root, base_commit, head_commit: [],
    )
    monkeypatch.setattr(
        "scripts.release.prepare_release_pr.version_plan.build_version_plan",
        lambda **kwargs: {"units": []},
    )
    monkeypatch.setattr(
        "scripts.release.prepare_release_pr.shutil.which",
        lambda name: None,
    )

    mutation_called = {"value": False}

    def _forbid_mutation(**kwargs: object) -> None:
        mutation_called["value"] = True

    monkeypatch.setattr(
        "scripts.release.prepare_release_pr.apply_versions.apply_version_updates",
        _forbid_mutation,
    )

    with pytest.raises(RuntimeError, match="uv executable not found on PATH"):
        prepare_release_pr.main()
    assert mutation_called["value"] is False
