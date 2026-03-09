"""Tests for selective release version planning."""

from __future__ import annotations

from pathlib import Path

from scripts.release import common, version_plan


def _unit(
    unit_id: str,
    name: str,
    version: str,
    dependencies: tuple[str, ...] = (),
) -> common.WorkspaceUnit:
    return common.WorkspaceUnit(
        unit_id=unit_id,
        path=Path(unit_id),
        project_name=name,
        version=version,
        dependencies=dependencies,
    )


def test_bump_level_detects_major_then_minor_then_patch() -> None:
    assert common.determine_bump_level(["feat!: break api"]) == "major"
    assert (
        common.determine_bump_level(["feat(upload): add chunking"]) == "minor"
    )
    assert (
        common.determine_bump_level(["fix(upload): retry edge case"]) == "patch"
    )


def test_build_version_plan_deterministic_and_dependency_propagation() -> None:
    units = {
        "packages/nova_file_api": _unit(
            "packages/nova_file_api",
            "nova-file-api",
            "0.1.0",
        ),
        "packages/nova_dash_bridge": _unit(
            "packages/nova_dash_bridge",
            "nova-dash-bridge",
            "0.1.0",
            dependencies=("nova-file-api>=0.1.0",),
        ),
    }

    changed_report = {
        "base_commit": "a",
        "head_commit": "b",
        "first_release": False,
        "changed_units": [{"unit_id": "packages/nova_file_api"}],
    }

    plan = version_plan.build_version_plan(
        units=units,
        changed_report=changed_report,
        commit_messages=["feat(api)!: change presign contract"],
        forced_bump=None,
    )

    payload = {item["unit_id"]: item for item in plan["units"]}
    assert payload["packages/nova_file_api"]["new_version"] == "1.0.0"
    assert payload["packages/nova_file_api"]["format"] == "pypi"
    assert payload["packages/nova_dash_bridge"]["reason"] == (
        "dependency_interface_change"
    )
    assert payload["packages/nova_dash_bridge"]["new_version"] == "0.1.1"


def test_no_changed_units_is_noop() -> None:
    units = {
        "packages/nova_file_api": _unit(
            "packages/nova_file_api",
            "nova-file-api",
            "0.1.0",
        )
    }
    changed_report = {
        "base_commit": "a",
        "head_commit": "b",
        "first_release": False,
        "changed_units": [],
    }

    plan = version_plan.build_version_plan(
        units=units,
        changed_report=changed_report,
        commit_messages=["docs: no code"],
        forced_bump=None,
    )

    assert plan["units"] == []
