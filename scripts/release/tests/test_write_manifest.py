"""Tests for release manifest rendering."""

from __future__ import annotations

from pathlib import Path

from scripts.release import common, write_manifest


def test_render_manifest_includes_schema_and_versions() -> None:
    units = {
        "packages/nova_file_api": common.WorkspaceUnit(
            unit_id="packages/nova_file_api",
            path=Path("packages/nova_file_api"),
            project_name="nova-file-api",
            version="0.1.0",
            dependencies=(),
        )
    }
    changed_report = {
        "base_commit": "abc",
        "head_commit": "def",
        "first_release": False,
        "changed_units": [{"unit_id": "packages/nova_file_api"}],
    }
    version_plan = {
        "global_bump": "patch",
        "units": [
            {
                "unit_id": "packages/nova_file_api",
                "new_version": "0.1.1",
            }
        ],
    }

    text = write_manifest.render_manifest(
        units=units,
        changed_report=changed_report,
        version_plan=version_plan,
        external_versions=[("container-craft", "0.0.0")],
    )

    assert "# Release Version Manifest" in text
    assert "## changed-units.json Schema" in text
    assert "`packages/nova_file_api`" in text
    assert "`0.1.1`" in text
