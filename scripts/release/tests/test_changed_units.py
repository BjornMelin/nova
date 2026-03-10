"""Tests for changed unit detection."""

from __future__ import annotations

from pathlib import Path

from scripts.release import changed_units, common


def _unit(unit_id: str, name: str) -> common.WorkspaceUnit:
    return common.WorkspaceUnit(
        unit_id=unit_id,
        path=Path(unit_id),
        project_name=name,
        version="0.1.0",
        dependencies=(),
    )


def test_build_changed_units_report_uses_path_mapping() -> None:
    units = {
        "packages/nova_file_api": _unit(
            "packages/nova_file_api",
            "nova-file-api",
        ),
        "packages/nova_dash_bridge": _unit(
            "packages/nova_dash_bridge",
            "nova-dash-bridge",
        ),
    }

    report = changed_units.build_changed_units_report(
        units=units,
        changed_files=["packages/nova_file_api/src/nova_file_api/app.py"],
        base_commit="abc",
        head_commit="def",
        first_release=False,
    )

    changed_ids = {item["unit_id"] for item in report["changed_units"]}
    assert changed_ids == {"packages/nova_file_api"}
    assert report["changed_units"][0]["format"] == "pypi"
    assert report["changed_units"][0]["namespace"] is None


def test_build_changed_units_report_first_release_marks_all_units() -> None:
    units = {
        "packages/nova_file_api": _unit(
            "packages/nova_file_api",
            "nova-file-api",
        ),
        "packages/nova_auth_api": _unit(
            "packages/nova_auth_api",
            "nova-auth-api",
        ),
    }

    report = changed_units.build_changed_units_report(
        units=units,
        changed_files=[],
        base_commit=None,
        head_commit="def",
        first_release=True,
    )

    changed_ids = {item["unit_id"] for item in report["changed_units"]}
    assert changed_ids == {
        "packages/nova_file_api",
        "packages/nova_auth_api",
    }


def test_build_changed_units_report_ignores_service_dockerfile_only_changes() -> None:
    units = {
        "packages/nova_file_api": _unit(
            "packages/nova_file_api",
            "nova-file-api",
        ),
        "packages/nova_auth_api": _unit(
            "packages/nova_auth_api",
            "nova-auth-api",
        ),
    }

    report = changed_units.build_changed_units_report(
        units=units,
        changed_files=["apps/nova_file_api_service/Dockerfile"],
        base_commit="abc",
        head_commit="def",
        first_release=False,
    )

    assert report["changed_units"] == []
