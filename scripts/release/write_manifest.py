"""Write release version manifest from release artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from . import common


def _external_versions_from_manifest(
    existing_text: str,
) -> list[tuple[str, str]]:
    marker = "## Participating External Repositories"
    if marker not in existing_text:
        return []

    after = existing_text.split(marker, maxsplit=1)[1]
    values: list[tuple[str, str]] = []
    for line in after.splitlines():
        if not line.startswith("- "):
            continue
        payload = line.removeprefix("- ").strip()
        if ":" not in payload:
            continue
        name, version = payload.split(":", maxsplit=1)
        values.append((name.strip().strip("`"), version.strip().strip("`")))
    return values


def render_manifest(
    *,
    units: dict[str, common.WorkspaceUnit],
    changed_report: dict[str, Any],
    version_plan: dict[str, Any],
    external_versions: list[tuple[str, str]],
) -> str:
    """Render markdown release manifest."""
    planned = {
        str(item["unit_id"]): str(item["new_version"])
        for item in version_plan.get("units", [])
    }
    changed_ids = {
        str(item["unit_id"]) for item in changed_report.get("changed_units", [])
    }

    lines: list[str] = []
    lines.append("# Release Version Manifest")
    lines.append("")
    lines.append(f"Date: {common.iso_timestamp()}")
    lines.append("Status: Active")
    lines.append("Schema: 1.0")
    lines.append("")
    lines.append("## Release Metadata")
    lines.append(f"- `base_commit`: `{changed_report.get('base_commit')}`")
    lines.append(f"- `head_commit`: `{changed_report.get('head_commit')}`")
    lines.append(
        f"- `first_release`: `{changed_report.get('first_release', False)}`"
    )
    lines.append(f"- `global_bump`: `{version_plan.get('global_bump')}`")
    lines.append("")
    lines.append("## changed-units.json Schema")
    lines.append("")
    lines.append("```json")
    lines.append("{")
    lines.append('  "schema_version": "1.0",')
    lines.append('  "base_commit": "<git-commit-or-null>",')
    lines.append('  "head_commit": "<git-commit>",')
    lines.append('  "first_release": true,')
    lines.append('  "changed_files": ["path/to/file.py"],')
    lines.append('  "changed_units": [')
    lines.append("    {")
    lines.append('      "unit_id": "packages/nova_file_api",')
    lines.append('      "project": "nova-file-api",')
    lines.append('      "path": "packages/nova_file_api",')
    lines.append('      "version": "0.1.0"')
    lines.append("    }")
    lines.append("  ]")
    lines.append("}")
    lines.append("```")
    lines.append("")
    lines.append("## Canonical Runtime Monorepo")
    lines.append("")
    lines.append("| Unit | Package | Version | Changed |")
    lines.append("| --- | --- | --- | --- |")

    for unit_id in sorted(units):
        unit = units[unit_id]
        version = planned.get(unit_id, unit.version)
        changed = "yes" if unit_id in changed_ids else "no"
        lines.append(
            f"| `{unit_id}` | `{unit.project_name}` | `{version}` | {changed} |"
        )

    lines.append("")
    lines.append("## Participating External Repositories")
    lines.append("")
    if external_versions:
        for name, version in external_versions:
            lines.append(f"- `{name}`: `{version}`")
    else:
        lines.append("- `container-craft`: `0.0.0`")
        lines.append("- `pca_analysis_dash`: `0.2.0`")

    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse command line options."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--changed-units", default="changed-units.json")
    parser.add_argument("--version-plan", default="version-plan.json")
    parser.add_argument("--manifest-path", default=common.DEFAULT_MANIFEST_PATH)
    return parser.parse_args()


def main() -> int:
    """Render and write release manifest markdown."""
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    units = common.load_workspace_units(repo_root)

    changed_path = Path(args.changed_units)
    if not changed_path.is_absolute():
        changed_path = repo_root / changed_path
    version_plan_path = Path(args.version_plan)
    if not version_plan_path.is_absolute():
        version_plan_path = repo_root / version_plan_path

    changed_report = common.read_json(changed_path)
    version_plan = common.read_json(version_plan_path)

    manifest_path = Path(args.manifest_path)
    if not manifest_path.is_absolute():
        manifest_path = repo_root / manifest_path
    previous = (
        manifest_path.read_text(encoding="utf-8")
        if manifest_path.exists()
        else ""
    )
    external_versions = _external_versions_from_manifest(previous)
    text = render_manifest(
        units=units,
        changed_report=changed_report,
        version_plan=version_plan,
        external_versions=external_versions,
    )

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(text, encoding="utf-8")
    print(f"manifest written: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
