"""Tests for CodeArtifact release gate validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

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


def _create_test_workspace_with_npm(root: Path) -> Path:
    repo_root = root / "repo"
    repo_root.mkdir()

    (repo_root / "pyproject.toml").write_text(
        "[tool.uv]\n\n[tool.uv.workspace]\nmembers = []\n",
        encoding="utf-8",
    )
    (repo_root / "package.json").write_text(
        "{\n"
        '  "private": true,\n'
        '  "workspaces": ["packages/nova_sdk_fetch"]\n'
        "}\n",
        encoding="utf-8",
    )
    unit_dir = repo_root / "packages" / "nova_sdk_fetch"
    unit_dir.mkdir(parents=True)
    unit_dir.joinpath("package.json").write_text(
        "{\n"
        '  "name": "@nova/sdk-fetch",\n'
        '  "version": "0.2.0",\n'
        '  "novaRelease": {"managed": true, "namespace": "nova"}\n'
        "}\n",
        encoding="utf-8",
    )
    return repo_root


def _create_test_workspace_with_r(root: Path) -> Path:
    repo_root = root / "repo"
    repo_root.mkdir()

    (repo_root / "pyproject.toml").write_text(
        "[tool.uv]\n\n"
        "[tool.nova.release]\n"
        "\n[[tool.nova.release.units]]\n"
        'unit_id = "packages/nova_sdk_r_file"\n'
        'path = "packages/nova_sdk_r_file"\n'
        'project_name = "nova.sdk.r.file"\n'
        "dependencies = []\n"
        'format = "r"\n'
        'codeartifact_format = "generic"\n'
        'namespace = "nova"\n',
        encoding="utf-8",
    )
    unit_dir = repo_root / "packages" / "nova_sdk_r_file"
    unit_dir.mkdir(parents=True)
    unit_dir.joinpath("DESCRIPTION").write_text(
        "Package: nova.sdk.r.file\nVersion: 0.2.0\n",
        encoding="utf-8",
    )
    return repo_root


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_r_publish_report(path: Path, *, unit_id: str) -> None:
    _write_json(
        path,
        {
            "schema_version": "1.0",
            "generated_at": "2026-03-09T00:00:00Z",
            "packages": [
                {
                    "unit_id": unit_id,
                    "package": "nova.sdk.r.file",
                    "version": "0.2.0",
                    "format": "r",
                    "codeartifact_format": "generic",
                    "namespace": "nova",
                    "tarball_path": f"{unit_id}/nova.sdk.r.file_0.2.0.tar.gz",
                    "signature_path": (
                        f"{unit_id}/nova.sdk.r.file_0.2.0.tar.gz.sig"
                    ),
                    "tarball_sha256": "a" * 64,
                    "signature_sha256": "b" * 64,
                }
            ],
        },
    )


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


def test_validate_release_gates_allows_non_r_release_without_r_evidence(
    tmp_path: Path,
) -> None:
    """No-R releases should not require R publish evidence."""
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

    report = codeartifact_gate.validate_release_gates(
        repo_root=repo_root,
        manifest_path=manifest,
        changed_units_path=changed_units,
        version_plan_path=version_plan,
        expected_manifest_sha256=None,
    )

    assert report["promotion_candidates"] == [
        {
            "format": "pypi",
            "codeartifact_format": "pypi",
            "namespace": None,
            "package": "nova-file-api",
            "version": "0.2.0",
            "unit_id": "packages/nova_file_api",
        }
    ]


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
            expected_manifest_sha256="a" * 64,
        )


def test_validate_release_gates_rejects_invalid_expected_sha_format(
    tmp_path: Path,
) -> None:
    repo_root = _create_test_workspace(tmp_path)
    manifest = tmp_path / "manifest.md"
    manifest.write_text(MANIFEST_TEXT, encoding="utf-8")

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
        match="expected manifest sha256 must be a 64-character hex digest",
    ):
        codeartifact_gate.validate_release_gates(
            repo_root=repo_root,
            manifest_path=manifest,
            changed_units_path=changed_units,
            version_plan_path=version_plan,
            expected_manifest_sha256="not-a-sha",
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
    repo_root = _create_test_workspace(tmp_path)
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


def test_validate_release_gates_rejects_duplicate_changed_units_entries(
    tmp_path: Path,
) -> None:
    repo_root = _create_test_workspace(tmp_path)
    manifest = tmp_path / "manifest.md"
    manifest.write_text(MANIFEST_TEXT, encoding="utf-8")
    changed_units = tmp_path / "changed-units.json"
    _write_json(
        changed_units,
        {
            "changed_units": [
                {"unit_id": "packages/nova_file_api"},
                {"unit_id": "packages/nova_file_api"},
            ]
        },
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
        match="duplicate changed_units unit_id",
    ):
        codeartifact_gate.validate_release_gates(
            repo_root=repo_root,
            manifest_path=manifest,
            changed_units_path=changed_units,
            version_plan_path=version_plan,
            expected_manifest_sha256=None,
        )


def test_validate_release_gates_supports_npm_candidates(
    tmp_path: Path,
) -> None:
    """Validate gate output supports npm promotion candidates."""
    repo_root = _create_test_workspace_with_npm(tmp_path)
    manifest_text = """# Release Version Manifest

Status: Active
Schema: 1.0

## Canonical Runtime Monorepo

| Unit | Package | Version | Changed |
| --- | --- | --- | --- |
| `packages/nova_sdk_fetch` | `@nova/sdk-fetch` | `0.2.0` | yes |
"""
    manifest = tmp_path / "manifest.md"
    manifest.write_text(manifest_text, encoding="utf-8")

    changed_units = tmp_path / "changed-units.json"
    _write_json(
        changed_units,
        {
            "changed_units": [{"unit_id": "packages/nova_sdk_fetch"}],
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
                    "unit_id": "packages/nova_sdk_fetch",
                    "format": "npm",
                    "codeartifact_format": "npm",
                    "namespace": "nova",
                    "new_version": "0.2.0",
                }
            ],
        },
    )

    report = codeartifact_gate.validate_release_gates(
        repo_root=repo_root,
        manifest_path=manifest,
        changed_units_path=changed_units,
        version_plan_path=version_plan,
        expected_manifest_sha256=None,
    )

    assert report["promotion_candidates"] == [
        {
            "format": "npm",
            "codeartifact_format": "npm",
            "namespace": "nova",
            "package": "@nova/sdk-fetch",
            "version": "0.2.0",
            "unit_id": "packages/nova_sdk_fetch",
        }
    ]


def test_validate_release_gates_supports_generic_r_candidates(
    tmp_path: Path,
) -> None:
    """Validate gate output supports generic R promotion candidates."""
    repo_root = _create_test_workspace_with_r(tmp_path)
    manifest_text = """# Release Version Manifest

Status: Active
Schema: 1.0

## Canonical Runtime Monorepo

| Unit | Package | Version | Changed |
| --- | --- | --- | --- |
| `packages/nova_sdk_r_file` | `nova.sdk.r.file` | `0.2.0` | yes |
"""
    manifest = tmp_path / "manifest.md"
    manifest.write_text(manifest_text, encoding="utf-8")

    changed_units = tmp_path / "changed-units.json"
    _write_json(
        changed_units,
        {
            "changed_units": [{"unit_id": "packages/nova_sdk_r_file"}],
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
                    "unit_id": "packages/nova_sdk_r_file",
                    "format": "r",
                    "codeartifact_format": "generic",
                    "namespace": "nova",
                    "new_version": "0.2.0",
                }
            ],
        },
    )
    r_publish_report = tmp_path / "r-publish-report.json"
    _write_r_publish_report(
        r_publish_report, unit_id="packages/nova_sdk_r_file"
    )

    report = codeartifact_gate.validate_release_gates(
        repo_root=repo_root,
        manifest_path=manifest,
        changed_units_path=changed_units,
        version_plan_path=version_plan,
        expected_manifest_sha256=None,
        r_publish_report_path=r_publish_report,
    )

    assert report["promotion_candidates"] == [
        {
            "format": "r",
            "codeartifact_format": "generic",
            "namespace": "nova",
            "package": "nova.sdk.r.file",
            "version": "0.2.0",
            "unit_id": "packages/nova_sdk_r_file",
            "tarball_sha256": "a" * 64,
            "signature_sha256": "b" * 64,
        }
    ]


def test_main_writes_canonical_non_r_candidates_without_evidence_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI output should omit evidence keys for non-R promotion candidates."""
    repo_root = _create_test_workspace_with_npm(tmp_path)
    manifest_text = """# Release Version Manifest

Status: Active
Schema: 1.0

## Canonical Runtime Monorepo

| Unit | Package | Version | Changed |
| --- | --- | --- | --- |
| `packages/nova_sdk_fetch` | `@nova/sdk-fetch` | `0.2.0` | yes |
"""
    manifest = tmp_path / "manifest.md"
    manifest.write_text(manifest_text, encoding="utf-8")

    changed_units = tmp_path / "changed-units.json"
    _write_json(
        changed_units,
        {
            "changed_units": [{"unit_id": "packages/nova_sdk_fetch"}],
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
                    "unit_id": "packages/nova_sdk_fetch",
                    "format": "npm",
                    "codeartifact_format": "npm",
                    "namespace": "nova",
                    "new_version": "0.2.0",
                }
            ],
        },
    )
    gate_report_out = tmp_path / "gate-report.json"
    candidates_out = tmp_path / "codeartifact-promotion-candidates.json"

    monkeypatch.setattr(
        codeartifact_gate,
        "parse_args",
        lambda: SimpleNamespace(
            repo_root=str(repo_root),
            manifest_path=str(manifest),
            changed_units=str(changed_units),
            version_plan=str(version_plan),
            expected_manifest_sha256=None,
            r_publish_report=None,
            gate_report_out=str(gate_report_out),
            promotion_candidates_out=str(candidates_out),
        ),
    )

    assert codeartifact_gate.main() == 0
    assert json.loads(candidates_out.read_text(encoding="utf-8")) == [
        {
            "format": "npm",
            "codeartifact_format": "npm",
            "namespace": "nova",
            "package": "@nova/sdk-fetch",
            "version": "0.2.0",
            "unit_id": "packages/nova_sdk_fetch",
        }
    ]


def test_validate_release_gates_rejects_r_candidates_without_evidence(
    tmp_path: Path,
) -> None:
    """R candidates must be accompanied by signed tarball evidence."""
    repo_root = _create_test_workspace_with_r(tmp_path)
    manifest_text = """# Release Version Manifest

Status: Active
Schema: 1.0

## Canonical Runtime Monorepo

| Unit | Package | Version | Changed |
| --- | --- | --- | --- |
| `packages/nova_sdk_r_file` | `nova.sdk.r.file` | `0.2.0` | yes |
"""
    manifest = tmp_path / "manifest.md"
    manifest.write_text(manifest_text, encoding="utf-8")

    changed_units = tmp_path / "changed-units.json"
    _write_json(
        changed_units,
        {
            "changed_units": [{"unit_id": "packages/nova_sdk_r_file"}],
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
                    "unit_id": "packages/nova_sdk_r_file",
                    "format": "r",
                    "codeartifact_format": "generic",
                    "namespace": "nova",
                    "new_version": "0.2.0",
                }
            ],
        },
    )

    with pytest.raises(
        codeartifact_gate.GateError,
        match="R release candidates require signed tarball evidence",
    ):
        codeartifact_gate.validate_release_gates(
            repo_root=repo_root,
            manifest_path=manifest,
            changed_units_path=changed_units,
            version_plan_path=version_plan,
            expected_manifest_sha256=None,
        )
