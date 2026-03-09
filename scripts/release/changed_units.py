"""Generate changed-units.json for selective release planning."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from . import common


def build_changed_units_report(
    *,
    units: dict[str, common.WorkspaceUnit],
    changed_files: list[str],
    base_commit: str | None,
    head_commit: str,
    first_release: bool,
) -> dict[str, Any]:
    """Build a changed-unit report payload."""
    if first_release:
        changed_ids = sorted(units)
    else:
        changed_ids = sorted(
            common.detect_changed_unit_ids(changed_files, units)
        )

    changed_units = [
        {
            "unit_id": unit_id,
            "project": units[unit_id].project_name,
            "path": unit_id,
            "version": units[unit_id].version,
            "format": units[unit_id].package_format,
            "namespace": units[unit_id].namespace,
        }
        for unit_id in changed_ids
    ]

    return {
        "schema_version": "1.0",
        "generated_at": common.iso_timestamp(),
        "base_commit": base_commit,
        "head_commit": head_commit,
        "first_release": first_release,
        "changed_files": changed_files,
        "changed_units": changed_units,
    }


def parse_args() -> argparse.Namespace:
    """Parse command line options."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--manifest-path", default=common.DEFAULT_MANIFEST_PATH)
    parser.add_argument("--base-commit", default=None)
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--output", default="changed-units.json")
    return parser.parse_args()


def main() -> int:
    """Generate changed unit report and write it to disk."""
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    units = common.load_workspace_units(repo_root)
    head_commit = common.run_git(repo_root, ["rev-parse", args.head_ref])

    base_commit = args.base_commit
    if base_commit is None:
        base_commit = common.find_manifest_base_commit(
            repo_root,
            manifest_path=args.manifest_path,
        )

    first_release = base_commit is None
    changed_files = common.list_changed_files(
        repo_root,
        head_commit=head_commit,
        base_commit=base_commit,
    )
    report = build_changed_units_report(
        units=units,
        changed_files=changed_files,
        base_commit=base_commit,
        head_commit=head_commit,
        first_release=first_release,
    )

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    common.write_json(output_path, report)

    print(
        "changed-units: "
        f"first_release={report['first_release']} "
        f"count={len(report['changed_units'])} "
        f"output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
