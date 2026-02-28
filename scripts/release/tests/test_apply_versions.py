"""Tests for applying selective versions to pyproject files."""

from __future__ import annotations

from pathlib import Path

from scripts.release import apply_versions, common


def _write_pyproject(path: Path, name: str, version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "[project]",
                f'name = "{name}"',
                f'version = "{version}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_apply_version_updates_changes_only_planned_units(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    file_api = repo_root / "packages/nova_file_api/pyproject.toml"
    dash = repo_root / "packages/nova_dash_bridge/pyproject.toml"
    _write_pyproject(file_api, "nova-file-api", "0.1.0")
    _write_pyproject(dash, "nova-dash-bridge", "0.1.0")

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
