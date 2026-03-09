"""Generate selective version bump plan from changed units."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, cast

from . import common


def build_version_plan(
    *,
    units: dict[str, common.WorkspaceUnit],
    changed_report: dict[str, Any],
    commit_messages: list[str],
    forced_bump: common.BumpLevel | None,
) -> dict[str, Any]:
    """Build a deterministic version plan payload."""
    changed_ids = {
        str(item["unit_id"]) for item in changed_report.get("changed_units", [])
    }
    if changed_report.get("first_release", False):
        changed_ids = set(units)

    if not changed_ids:
        return {
            "schema_version": "1.0",
            "generated_at": common.iso_timestamp(),
            "base_commit": changed_report.get("base_commit"),
            "head_commit": changed_report.get("head_commit"),
            "global_bump": None,
            "units": [],
        }

    unknown_unit_ids = sorted(changed_ids - set(units))
    if unknown_unit_ids:
        raise ValueError(
            "changed-units report references unknown units: "
            + ", ".join(unknown_unit_ids)
        )

    bump_level = forced_bump or common.determine_bump_level(commit_messages)

    plan_by_unit: dict[str, dict[str, str | None]] = {}
    for unit_id in sorted(changed_ids):
        unit = units[unit_id]
        plan_by_unit[unit_id] = {
            "unit_id": unit_id,
            "project": unit.project_name,
            "path": unit_id,
            "format": unit.package_format,
            "namespace": unit.namespace,
            "old_version": unit.version,
            "new_version": common.increment_semver(unit.version, bump_level),
            "bump": bump_level,
            "reason": "changed",
        }

    if bump_level in {"major", "minor"}:
        changed_packages = {
            units[unit_id].project_name for unit_id in changed_ids
        }
        dependents = common.find_dependents(units, changed_packages)
        for dependent_unit in sorted(dependents):
            if dependent_unit in plan_by_unit:
                continue
            unit = units[dependent_unit]
            plan_by_unit[dependent_unit] = {
                "unit_id": dependent_unit,
                "project": unit.project_name,
                "path": dependent_unit,
                "format": unit.package_format,
                "namespace": unit.namespace,
                "old_version": unit.version,
                "new_version": common.increment_semver(
                    unit.version,
                    "patch",
                ),
                "bump": "patch",
                "reason": "dependency_interface_change",
            }

    return {
        "schema_version": "1.0",
        "generated_at": common.iso_timestamp(),
        "base_commit": changed_report.get("base_commit"),
        "head_commit": changed_report.get("head_commit"),
        "global_bump": bump_level,
        "units": [plan_by_unit[key] for key in sorted(plan_by_unit)],
    }


def parse_args() -> argparse.Namespace:
    """Parse command line options."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--changed-units", default="changed-units.json")
    parser.add_argument("--output", default="version-plan.json")
    parser.add_argument("--force-bump", choices=["major", "minor", "patch"])
    return parser.parse_args()


def main() -> int:
    """Generate selective version plan based on changed units and commits."""
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    units = common.load_workspace_units(repo_root)

    changed_path = Path(args.changed_units)
    if not changed_path.is_absolute():
        changed_path = repo_root / changed_path
    changed_report = common.read_json(changed_path)

    base_commit = changed_report.get("base_commit")
    head_commit = changed_report.get("head_commit")
    if not isinstance(head_commit, str):
        raise ValueError("changed-units report missing head_commit")

    commit_messages = common.collect_commit_messages(
        repo_root,
        base_commit=base_commit,
        head_commit=head_commit,
    )
    version_plan = build_version_plan(
        units=units,
        changed_report=changed_report,
        commit_messages=commit_messages,
        forced_bump=cast(common.BumpLevel | None, args.force_bump),
    )

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    common.write_json(output_path, version_plan)

    print(
        "version-plan: "
        f"units={len(version_plan['units'])} "
        f"bump={version_plan.get('global_bump')} "
        f"output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
