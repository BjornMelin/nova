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


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _repo_root() -> Path:
    marker = Path(__file__).resolve()
    for parent in (marker, *marker.parents):
        if (parent / ".git").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("Could not resolve repository root for tests")


def test_validate_release_gates_success(tmp_path: Path) -> None:
    """Verify valid gate inputs produce a successful gate report.

    Args:
        tmp_path:
            Temporary directory used for test manifest and JSON fixtures.

    Returns:
        None:
            Test passes when assertions hold and no exceptions are raised.
    """
    repo_root = _repo_root()
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


def test_validate_release_gates_rejects_manifest_mismatch(
    tmp_path: Path,
) -> None:
    """Verify manifest/package mismatches are rejected with a GateError.

    Args:
        tmp_path:
            Temporary directory used for manifest and input fixtures.

    Returns:
        None:
            Test passes when the expected GateError is raised.

    """
    repo_root = _repo_root()
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
        codeartifact_gate.GateError, match="manifest/package version mismatch"
    ):
        codeartifact_gate.validate_release_gates(
            repo_root=repo_root,
            manifest_path=manifest,
            changed_units_path=changed_units,
            version_plan_path=version_plan,
            expected_manifest_sha256=None,
        )


def test_validate_release_gates_rejects_changed_units_plan_drift(
    tmp_path: Path,
) -> None:
    """Verify drift between changed units and version-plan units is rejected.

    Args:
        tmp_path:
            Temporary directory used for manifest and input fixtures.

    Returns:
        None:
            Test passes when the expected GateError is raised.

    """
    repo_root = _repo_root()
    manifest = tmp_path / "manifest.md"
    manifest.write_text(MANIFEST_TEXT, encoding="utf-8")

    changed_units = tmp_path / "changed-units.json"
    _write_json(
        changed_units,
        {
            "changed_units": [
                {"unit_id": "packages/nova_file_api"},
                {"unit_id": "packages/nova_auth_api"},
            ]
        },
    )

    version_plan = tmp_path / "version-plan.json"
    _write_json(
        version_plan,
        {
            "units": [
                {
                    "unit_id": "packages/nova_file_api",
                    "new_version": "0.2.0",
                }
            ]
        },
    )

    with pytest.raises(codeartifact_gate.GateError, match="must match exactly"):
        codeartifact_gate.validate_release_gates(
            repo_root=repo_root,
            manifest_path=manifest,
            changed_units_path=changed_units,
            version_plan_path=version_plan,
            expected_manifest_sha256=None,
        )
