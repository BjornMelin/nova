"""Tests for CodeArtifact release gate validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.release import codeartifact_gate

MANIFEST_TEXT = """# Release Version Manifest

Status: Active
Schema: 1.0

## Canonical Runtime Monorepo

| Unit | Package | Version | Changed |
| --- | --- | --- | --- |
| `packages/nova_file_api` | `nova-file-api` | `0.2.0` | yes |
"""


def _create_test_workspace(root: Path) -> Path:
    repo_root = root / "repo"
    repo_root.mkdir()

    workspace_text = (
        "[tool.uv]\n\n"
        "[tool.uv.workspace]\n"
        'members = ["packages/nova_file_api"]\n'
    )
    (repo_root / "pyproject.toml").write_text(workspace_text, encoding="utf-8")
    (repo_root / "packages").mkdir()
    unit_dir = repo_root / "packages" / "nova_file_api"
    unit_dir.mkdir(parents=True)
    unit_dir.joinpath("pyproject.toml").write_text(
        "[project]\n"
        'name = "nova-file-api"\n'
        'version = "0.2.0"\n'
        "dependencies = []\n",
        encoding="utf-8",
    )
    return repo_root


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_validate_release_gates_success(tmp_path: Path) -> None:
    """Validate gate success path for a matching manifest and version plan."""
    repo_root = _create_test_workspace(tmp_path)
    manifest = tmp_path / "manifest.md"
    manifest.write_text(MANIFEST_TEXT, encoding="utf-8")

    changed_units = tmp_path / "changed-units.json"
    _write_json(
        changed_units,
        {
            "changed_units": [{"unit_id": "packages/nova_file_api"}],
            "base_commit": "abc",
            "head_commit": "def",
            "first_release": False,
        },
    )

    version_plan = tmp_path / "version-plan.json"
    _write_json(
        version_plan,
        {
            "global_bump": "patch",
            "units": [
                {
                    "unit_id": "packages/nova_file_api",
                    "new_version": "0.2.0",
                }
            ],
        },
    )

    expected_sha = hashlib.sha256(MANIFEST_TEXT.encode("utf-8")).hexdigest()
    report = codeartifact_gate.validate_release_gates(
        repo_root=repo_root,
        manifest_path=manifest,
        changed_units_path=changed_units,
        version_plan_path=version_plan,
        expected_manifest_sha256=expected_sha,
    )

    assert report["manifest_sha256"] == expected_sha
    assert report["planned_package_count"] == 1
    assert report["promotion_candidates"][0]["package"] == "nova-file-api"


def test_validate_release_gates_rejects_manifest_sha256_mismatch(
    tmp_path: Path,
) -> None:
    """Reject promotion when expected manifest SHA256 does not match."""
    repo_root = _create_test_workspace(tmp_path)
    manifest = tmp_path / "manifest.md"
    manifest.write_text(MANIFEST_TEXT, encoding="utf-8")

    changed_units = tmp_path / "changed-units.json"
    _write_json(
        changed_units,
        {
            "changed_units": [{"unit_id": "packages/nova_file_api"}],
            "base_commit": "abc",
            "head_commit": "def",
            "first_release": False,
        },
    )

    version_plan = tmp_path / "version-plan.json"
    _write_json(
        version_plan,
        {
            "global_bump": "patch",
            "units": [
                {
                    "unit_id": "packages/nova_file_api",
                    "new_version": "0.2.0",
                }
            ],
        },
    )

    with pytest.raises(
        codeartifact_gate.GateError,
        match="release manifest digest mismatch",
    ):
        codeartifact_gate.validate_release_gates(
            repo_root=repo_root,
            manifest_path=manifest,
            changed_units_path=changed_units,
            version_plan_path=version_plan,
            expected_manifest_sha256="badsum",
        )


def test_validate_release_gates_rejects_manifest_mismatch(
    tmp_path: Path,
) -> None:
    """Reject promotion when manifest package versions differ from plan."""
    repo_root = _create_test_workspace(tmp_path)
    manifest = tmp_path / "manifest.md"
    manifest.write_text(
        MANIFEST_TEXT.replace("0.2.0", "0.3.0"), encoding="utf-8"
    )

    changed_units = tmp_path / "changed-units.json"
    _write_json(
        changed_units,
        {"changed_units": [{"unit_id": "packages/nova_file_api"}]},
    )

    version_plan = tmp_path / "version-plan.json"
    _write_json(
        version_plan,
        {
            "units": [
                {"unit_id": "packages/nova_file_api", "new_version": "0.2.0"}
            ]
        },
    )

    with pytest.raises(
        codeartifact_gate.GateError,
        match="manifest/package version mismatch",
    ):
        codeartifact_gate.validate_release_gates(
            repo_root=repo_root,
            manifest_path=manifest,
            changed_units_path=changed_units,
            version_plan_path=version_plan,
            expected_manifest_sha256=None,
        )
