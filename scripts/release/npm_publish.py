"""Prepare publish-ready npm package artifacts from managed workspaces."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

from scripts.release import common

DEPENDENCY_FIELDS = (
    "dependencies",
    "optionalDependencies",
    "peerDependencies",
)
LOCAL_DEPENDENCY_SPEC_RE = re.compile(r"^(workspace:|file:|link:)")


def planned_version_map(
    *,
    version_plan: dict[str, Any],
    units: dict[str, common.WorkspaceUnit],
) -> dict[str, str]:
    """Return per-unit versions after applying the release plan."""
    versions = {unit_id: unit.version for unit_id, unit in units.items()}
    for item in version_plan.get("units", []):
        unit_id = str(item.get("unit_id", "")).strip()
        new_version = str(item.get("new_version", "")).strip()
        if unit_id and new_version:
            versions[unit_id] = new_version
    return versions


def collect_npm_unit_ids(
    *,
    version_plan: dict[str, Any],
    units: dict[str, common.WorkspaceUnit],
) -> list[str]:
    """Return planned npm unit IDs in dependency order."""
    npm_unit_ids: set[str] = set()
    for item in version_plan.get("units", []):
        unit_id = str(item.get("unit_id", "")).strip()
        if not unit_id:
            continue
        unit = units.get(unit_id)
        if unit is None:
            raise ValueError(
                f"version plan unit not found in workspace: {unit_id}"
            )
        if unit.package_format == "npm":
            npm_unit_ids.add(unit_id)
    return common.order_units_for_release(units, npm_unit_ids)


def prepare_npm_publish_artifacts(
    *,
    repo_root: Path,
    version_plan: dict[str, Any],
    units: dict[str, common.WorkspaceUnit],
    registry_url: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Create publish-ready npm directories with exact internal semver deps."""
    registry = registry_url.rstrip("/") + "/"
    version_by_unit = planned_version_map(
        version_plan=version_plan,
        units=units,
    )
    ordered_unit_ids = collect_npm_unit_ids(
        version_plan=version_plan,
        units=units,
    )
    if not ordered_unit_ids:
        return {
            "schema_version": "1.0",
            "generated_at": common.iso_timestamp(),
            "registry_url": registry,
            "packages": [],
        }

    package_name_to_unit = {
        common.parse_dependency_name(unit.project_name): unit_id
        for unit_id, unit in units.items()
        if unit.package_format == "npm"
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    packages: list[dict[str, Any]] = []

    for unit_id in ordered_unit_ids:
        unit = units[unit_id]
        if not (unit.path / "dist").exists():
            raise ValueError(
                "npm package "
                f"{unit.project_name} is missing a built dist/ directory"
            )

        target_dir = output_dir / unit.path.name
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(
            unit.path,
            target_dir,
            ignore=shutil.ignore_patterns("node_modules", "*.tsbuildinfo"),
        )
        package_path = target_dir / "package.json"
        package_data = json.loads(package_path.read_text(encoding="utf-8"))
        package_data["version"] = version_by_unit[unit_id]
        package_data.pop("private", None)
        package_data.pop("novaRelease", None)

        publish_config = package_data.get("publishConfig", {})
        if not isinstance(publish_config, dict):
            raise ValueError(
                f"publishConfig in {unit.project_name} must be an object"
            )
        publish_config["registry"] = registry
        package_data["publishConfig"] = publish_config

        for field in DEPENDENCY_FIELDS:
            raw_dependencies = package_data.get(field)
            if raw_dependencies is None:
                continue
            if not isinstance(raw_dependencies, dict):
                raise ValueError(
                    "package.json field "
                    f"{field} in {unit.project_name} must be an object"
                )
            for dependency_name in sorted(raw_dependencies):
                dependency_unit_id = package_name_to_unit.get(
                    common.parse_dependency_name(dependency_name)
                )
                if dependency_unit_id is None:
                    continue
                raw_dependencies[dependency_name] = version_by_unit[
                    dependency_unit_id
                ]

        package_path.write_text(
            json.dumps(package_data, indent=2) + "\n",
            encoding="utf-8",
        )
        validate_prepared_npm_package(package_path)
        try:
            publish_dir = str(target_dir.relative_to(repo_root))
        except ValueError:
            publish_dir = str(target_dir)

        packages.append(
            {
                "unit_id": unit_id,
                "package": unit.project_name,
                "namespace": unit.namespace,
                "version": version_by_unit[unit_id],
                "publish_dir": publish_dir,
            }
        )

    return {
        "schema_version": "1.0",
        "generated_at": common.iso_timestamp(),
        "registry_url": registry,
        "packages": packages,
    }


def validate_prepared_npm_package(package_json_path: Path) -> None:
    """Reject publish artifacts with remaining local-only dependency specs."""
    package_data = json.loads(package_json_path.read_text(encoding="utf-8"))
    for field in DEPENDENCY_FIELDS:
        raw_dependencies = package_data.get(field, {})
        if not isinstance(raw_dependencies, dict):
            raise ValueError(f"{package_json_path}: {field} must be an object")
        for dependency_name, dependency_version in raw_dependencies.items():
            if LOCAL_DEPENDENCY_SPEC_RE.match(str(dependency_version).strip()):
                raise ValueError(
                    f"{package_json_path}: dependency {dependency_name} "
                    "still uses a local-only specifier"
                )


def parse_args() -> argparse.Namespace:
    """Parse CLI options."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--version-plan", required=True)
    parser.add_argument("--registry-url", required=True)
    parser.add_argument("--output-dir", default=".artifacts/npm-publish")
    parser.add_argument(
        "--report-out",
        default=".artifacts/npm-publish-report.json",
    )
    return parser.parse_args()


def main() -> int:
    """Prepare npm publish artifacts and write a report."""
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    units = common.load_workspace_units(repo_root)

    version_plan_path = Path(args.version_plan)
    if not version_plan_path.is_absolute():
        version_plan_path = repo_root / version_plan_path
    version_plan = common.read_json(version_plan_path)

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    report = prepare_npm_publish_artifacts(
        repo_root=repo_root,
        version_plan=version_plan,
        units=units,
        registry_url=args.registry_url,
        output_dir=output_dir,
    )

    report_path = Path(args.report_out)
    if not report_path.is_absolute():
        report_path = repo_root / report_path
    common.write_json(report_path, report)
    print(
        "npm-publish-prep: "
        f"packages={len(report['packages'])} output={report_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
