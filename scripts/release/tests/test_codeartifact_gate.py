"""Tests for CodeArtifact release gate validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

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


def test_validate_release_gates_success(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
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
    repo_root = Path(__file__).resolve().parents[3]
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

    try:
        codeartifact_gate.validate_release_gates(
            repo_root=repo_root,
            manifest_path=manifest,
            changed_units_path=changed_units,
            version_plan_path=version_plan,
            expected_manifest_sha256=None,
        )
    except codeartifact_gate.GateError as exc:
        assert "manifest/package version mismatch" in str(exc)
    else:
        raise AssertionError("Expected GateError for manifest mismatch")
