"""Apply version plan updates to workspace manifests."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scripts.release import common

SEMVER_RE = re.compile(
    r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


def _replace_project_version(
    pyproject_text: str,
    old_version: str,
    new_version: str,
) -> str:
    project_header = re.search(r"(?m)^\[project\]\s*$", pyproject_text)
    if project_header is None:
        raise ValueError("[project] section not found")

    section_start = project_header.end()
    next_section = re.search(
        r"(?m)^\[[^\]]+\]\s*$",
        pyproject_text[section_start:],
    )
    section_end = (
        section_start + next_section.start()
        if next_section is not None
        else len(pyproject_text)
    )

    section_text = pyproject_text[section_start:section_end]
    pattern = re.compile(r"(?m)^version\s*=\s*\"([^\"]+)\"\s*$")
    match = pattern.search(section_text)
    if match is None:
        raise ValueError("project version field not found")
    if match.group(1) != old_version:
        raise ValueError(
            "planned old version does not match file: "
            f"expected {old_version}, found {match.group(1)}"
        )
    version_start = section_start + match.start(1)
    version_end = section_start + match.end(1)
    return (
        pyproject_text[:version_start]
        + new_version
        + pyproject_text[version_end:]
    )


def _replace_package_version(
    package_text: str,
    old_version: str,
    new_version: str,
) -> str:
    package_data = json.loads(package_text)
    current_version = str(package_data.get("version", "")).strip()
    if current_version != old_version:
        raise ValueError(
            "planned old version does not match file: "
            f"expected {old_version}, found {current_version}"
        )
    package_data["version"] = new_version
    return json.dumps(package_data, indent=2) + "\n"


def _replace_description_version(
    description_text: str,
    old_version: str,
    new_version: str,
) -> str:
    version_pattern = re.compile(r"(?m)^Version:\s*([^\n]+)\s*$")
    match = version_pattern.search(description_text)
    if match is None:
        raise ValueError("DESCRIPTION version field not found")
    if match.group(1).strip() != old_version:
        raise ValueError(
            "planned old version does not match file: "
            f"expected {old_version}, found {match.group(1).strip()}"
        )
    version_start = match.start(1)
    version_end = match.end(1)
    return (
        description_text[:version_start]
        + new_version
        + description_text[version_end:]
    )


def apply_version_updates(
    *,
    repo_root: Path,
    version_plan: dict[str, Any],
    units: dict[str, common.WorkspaceUnit],
    dry_run: bool,
) -> list[str]:
    """Apply version plan and return updated file paths.

    Args:
        repo_root: Repository root path.
        version_plan: Parsed version plan payload.
        units: Workspace units keyed by unit ID.
        dry_run: If true, report updates without writing files.

    Returns:
        Relative file paths updated by the version plan.

    Raises:
        KeyError: If a plan unit_id is missing from workspace units.
        ValueError: If a target manifest version does not match the plan.
        TypeError: If ``version_plan`` or ``version_plan["units"]`` has an
            invalid JSON structure.
    """
    if not isinstance(version_plan, Mapping):
        raise TypeError("version_plan must be a JSON object")
    raw_units = version_plan.get("units", [])
    if not isinstance(raw_units, list):
        raise TypeError("version_plan.units must be a JSON array")

    updated: list[str] = []
    seen_unit_ids: set[str] = set()
    for item in raw_units:
        if not isinstance(item, Mapping):
            raise TypeError("version plan units must be objects")
        unit_id = str(item.get("unit_id", "")).strip()
        old_version = str(item.get("old_version", "")).strip()
        new_version = str(item.get("new_version", "")).strip()
        if not unit_id:
            raise ValueError("version plan unit is missing unit_id")
        if unit_id in seen_unit_ids:
            raise ValueError(f"duplicate unit_id in version plan: {unit_id}")
        seen_unit_ids.add(unit_id)
        if unit_id not in units:
            raise ValueError(
                f"version plan unit not found in workspace: {unit_id}"
            )
        if not old_version or not SEMVER_RE.match(old_version):
            raise ValueError(
                "version plan old_version is invalid for "
                f"{unit_id}: {old_version}"
            )
        if not new_version or not SEMVER_RE.match(new_version):
            raise ValueError(
                "version plan new_version is invalid for "
                f"{unit_id}: {new_version}"
            )

        unit = units[unit_id]
        if unit.package_format == "npm":
            manifest_path = unit.path / "package.json"
            text = manifest_path.read_text(encoding="utf-8")
            replaced = _replace_package_version(text, old_version, new_version)
        elif unit.package_format == "pypi":
            manifest_path = unit.path / "pyproject.toml"
            text = manifest_path.read_text(encoding="utf-8")
            replaced = _replace_project_version(text, old_version, new_version)
        elif unit.package_format == "r":
            manifest_path = unit.path / "DESCRIPTION"
            text = manifest_path.read_text(encoding="utf-8")
            replaced = _replace_description_version(
                text,
                old_version,
                new_version,
            )
        else:
            raise ValueError(
                "unsupported package format for "
                f"{unit_id}: {unit.package_format}"
            )

        if replaced != text:
            updated.append(str(manifest_path.relative_to(repo_root)))
            if not dry_run:
                manifest_path.write_text(replaced, encoding="utf-8")

    return updated


def parse_args() -> argparse.Namespace:
    """Parse command line options.

    Returns:
        Parsed CLI namespace for apply_versions arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--version-plan", default="version-plan.json")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    """Apply selective versions to workspace units.

    Returns:
        Process exit code.
    """
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    units = common.load_workspace_units(repo_root)

    plan_path = Path(args.version_plan)
    if not plan_path.is_absolute():
        plan_path = repo_root / plan_path
    version_plan = common.read_json(plan_path)

    updated_files = apply_version_updates(
        repo_root=repo_root,
        version_plan=version_plan,
        units=units,
        dry_run=args.dry_run,
    )
    print(
        "apply-versions: "
        f"updated_files={len(updated_files)} dry_run={args.dry_run}"
    )
    for file_path in updated_files:
        print(f" - {file_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
