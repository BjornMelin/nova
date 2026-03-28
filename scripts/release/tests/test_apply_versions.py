"""Tests for applying selective versions to pyproject files."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.release import apply_versions, common


def _write_pyproject(
    write_text: Callable[[Path, str], None],
    path: Path,
    name: str,
    version: str,
) -> None:
    write_text(
        path,
        "\n".join(
            [
                "[project]",
                f'name = "{name}"',
                f'version = "{version}"',
            ]
        )
        + "\n",
    )


def _write_description(
    write_text: Callable[[Path, str], None],
    path: Path,
    name: str,
    version: str,
) -> None:
    write_text(
        path,
        "\n".join(
            [
                f"Package: {name}",
                f"Version: {version}",
            ]
        )
        + "\n",
    )


def _write_release_pyproject(
    write_text: Callable[[Path, str], None],
    path: Path,
    unit_id: str,
    project_name: str = "nova",
) -> None:
    write_text(
        path,
        "[tool.uv]\n\n"
        "[tool.nova.release]\n"
        "\n[[tool.nova.release.units]]\n"
        f'unit_id = "{unit_id}"\n'
        f'path = "{unit_id}"\n'
        f'project_name = "{project_name}"\n'
        "dependencies = []\n"
        'format = "r"\n'
        'codeartifact_format = "generic"\n'
        'namespace = "nova"\n',
    )


def test_apply_version_updates_changes_only_planned_units(
    tmp_path: Path,
    write_text: Callable[[Path, str], None],
) -> None:
    """Update only the workspace unit included in the version plan.

    Args:
        tmp_path: Temporary repo root used for the synthetic workspace.
        write_text: Helper that writes fixture files into the temp repo.

    Returns:
        None.
    """
    repo_root = tmp_path
    file_api = repo_root / "packages/nova_file_api/pyproject.toml"
    dash = repo_root / "packages/nova_dash_bridge/pyproject.toml"
    _write_pyproject(write_text, file_api, "nova-file-api", "0.1.0")
    _write_pyproject(write_text, dash, "nova-dash-bridge", "0.1.0")

    units = {
        "packages/nova_file_api": common.WorkspaceUnit(
            unit_id="packages/nova_file_api",
            path=file_api.parent,
            project_name="nova-file-api",
            version="0.1.0",
            dependencies=(),
        ),
        "packages/nova_dash_bridge": common.WorkspaceUnit(
            unit_id="packages/nova_dash_bridge",
            path=dash.parent,
            project_name="nova-dash-bridge",
            version="0.1.0",
            dependencies=(),
        ),
    }

    plan = {
        "units": [
            {
                "unit_id": "packages/nova_file_api",
                "old_version": "0.1.0",
                "new_version": "0.1.1",
            }
        ]
    }
    updated = apply_versions.apply_version_updates(
        repo_root=repo_root,
        version_plan=plan,
        units=units,
        dry_run=False,
    )

    assert updated == ["packages/nova_file_api/pyproject.toml"]
    assert 'version = "0.1.1"' in file_api.read_text(encoding="utf-8")
    assert 'version = "0.1.0"' in dash.read_text(encoding="utf-8")


def test_apply_version_updates_changes_r_description(
    tmp_path: Path,
    write_text: Callable[[Path, str], None],
) -> None:
    """Apply release-plan updates to R DESCRIPTION files only.

    Args:
        tmp_path: Temporary repo root used for the synthetic workspace.
        write_text: Helper that writes fixture files into the temp repo.

    Returns:
        None.
    """
    repo_root = tmp_path
    pyproject = repo_root / "pyproject.toml"
    _write_release_pyproject(
        write_text,
        pyproject,
        "packages/nova_sdk_r",
        project_name="nova",
    )
    original_pyproject = pyproject.read_text(encoding="utf-8")
    description = repo_root / "packages/nova_sdk_r/DESCRIPTION"
    _write_description(write_text, description, "nova", "0.1.0")

    units = {
        "packages/nova_sdk_r": common.WorkspaceUnit(
            unit_id="packages/nova_sdk_r",
            path=description.parent,
            project_name="nova",
            version="0.1.0",
            dependencies=(),
            package_format="r",
            codeartifact_format="generic",
            namespace="nova",
        )
    }
    plan = {
        "units": [
            {
                "unit_id": "packages/nova_sdk_r",
                "old_version": "0.1.0",
                "new_version": "0.1.1",
            }
        ]
    }

    updated = apply_versions.apply_version_updates(
        repo_root=repo_root,
        version_plan=plan,
        units=units,
        dry_run=False,
    )

    assert updated == ["packages/nova_sdk_r/DESCRIPTION"]
    assert pyproject.read_text(encoding="utf-8") == original_pyproject
    assert "Version: 0.1.1" in description.read_text(encoding="utf-8")


def test_apply_version_updates_changes_npm_package_json(
    tmp_path: Path,
    write_text: Callable[[Path, str], None],
) -> None:
    """Validate npm package.json versions are updated by the release plan."""
    repo_root = tmp_path
    package_json = repo_root / "packages/nova_sdk_ts/package.json"
    write_text(
        package_json,
        '{\n  "name": "@nova/sdk",\n  "version": "0.1.0"\n}\n',
    )

    units = {
        "packages/nova_sdk_ts": common.WorkspaceUnit(
            unit_id="packages/nova_sdk_ts",
            path=package_json.parent,
            project_name="@nova/sdk",
            version="0.1.0",
            dependencies=(),
            package_format="npm",
            namespace="nova",
        )
    }
    plan = {
        "units": [
            {
                "unit_id": "packages/nova_sdk_ts",
                "old_version": "0.1.0",
                "new_version": "0.1.1",
            }
        ]
    }

    updated = apply_versions.apply_version_updates(
        repo_root=repo_root,
        version_plan=plan,
        units=units,
        dry_run=False,
    )

    assert updated == ["packages/nova_sdk_ts/package.json"]
    assert '"version": "0.1.1"' in package_json.read_text(encoding="utf-8")


def test_apply_version_updates_rejects_unknown_unit_id(
    tmp_path: Path,
    write_text: Callable[[Path, str], None],
) -> None:
    """Reject version-plan entries that do not map to known workspace units.

    Args:
        tmp_path: Temporary repo root used for the synthetic workspace.
        write_text: Helper that writes fixture files into the temp repo.

    Returns:
        None.
    """
    repo_root = tmp_path
    file_api = repo_root / "packages/nova_file_api/pyproject.toml"
    _write_pyproject(write_text, file_api, "nova-file-api", "0.1.0")
    units = {
        "packages/nova_file_api": common.WorkspaceUnit(
            unit_id="packages/nova_file_api",
            path=file_api.parent,
            project_name="nova-file-api",
            version="0.1.0",
            dependencies=(),
        )
    }

    with pytest.raises(ValueError, match="not found in workspace"):
        apply_versions.apply_version_updates(
            repo_root=repo_root,
            version_plan={
                "units": [
                    {
                        "unit_id": "packages/unknown",
                        "old_version": "0.1.0",
                        "new_version": "0.1.1",
                    }
                ]
            },
            units=units,
            dry_run=True,
        )


def test_apply_version_updates_rejects_invalid_version_format(
    tmp_path: Path,
    write_text: Callable[[Path, str], None],
) -> None:
    """Reject release plans that specify non-semver target versions.

    Args:
        tmp_path: Temporary repo root used for the synthetic workspace.
        write_text: Helper that writes fixture files into the temp repo.

    Returns:
        None.
    """
    repo_root = tmp_path
    file_api = repo_root / "packages/nova_file_api/pyproject.toml"
    _write_pyproject(write_text, file_api, "nova-file-api", "0.1.0")
    units = {
        "packages/nova_file_api": common.WorkspaceUnit(
            unit_id="packages/nova_file_api",
            path=file_api.parent,
            project_name="nova-file-api",
            version="0.1.0",
            dependencies=(),
        )
    }

    with pytest.raises(ValueError, match="new_version is invalid"):
        apply_versions.apply_version_updates(
            repo_root=repo_root,
            version_plan={
                "units": [
                    {
                        "unit_id": "packages/nova_file_api",
                        "old_version": "0.1.0",
                        "new_version": "latest",
                    }
                ]
            },
            units=units,
            dry_run=True,
        )
