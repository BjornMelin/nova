"""Prepare publish-ready npm package artifacts from managed workspaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from scripts.release import common

DEPENDENCY_FIELDS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)
LOCAL_DEPENDENCY_SPEC_RE = re.compile(r"^(workspace:|file:|link:)")
SEMVER_RE = re.compile(
    r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


def _validated_planned_versions(version_plan: dict[str, Any]) -> dict[str, str]:
    """Return validated planned versions keyed by workspace unit ID.

    Args:
        version_plan: Release-plan payload containing planned unit versions.

    Returns:
        Mapping of workspace unit ID to validated target version.

    Raises:
        TypeError: If ``version_plan.units`` is not a JSON array or contains
            non-object entries.
        ValueError: If ``version_plan.units`` contains an
            invalid ``new_version`` for a planned unit.
    """
    raw_units = version_plan.get("units", [])
    if not isinstance(raw_units, list):
        raise TypeError("version_plan.units must be a JSON array")

    versions: dict[str, str] = {}
    for item in raw_units:
        if not isinstance(item, dict):
            raise TypeError("version_plan.units entries must be objects")
        unit_id = str(item.get("unit_id", "")).strip()
        new_version = str(item.get("new_version", "")).strip()
        if not unit_id:
            continue
        if not new_version:
            raise ValueError(
                f"version plan unit {unit_id} must declare new_version"
            )
        if not SEMVER_RE.match(new_version):
            raise ValueError(
                f"version plan unit {unit_id} has invalid semver: {new_version}"
            )
        if unit_id in versions:
            raise ValueError(f"duplicate unit_id in version plan: {unit_id}")
        versions[unit_id] = new_version
    return versions


def planned_version_map(
    *,
    version_plan: dict[str, Any],
    units: dict[str, common.WorkspaceUnit],
) -> dict[str, str]:
    """Return per-unit versions after applying the release plan.

    Args:
        version_plan: Release-plan payload with unit/version changes.
        units: Workspace units keyed by unit ID.

    Returns:
        Mapping of every workspace unit ID to the version that should be
        published after applying the release plan.

    Raises:
        ValueError: If planned unit versions are missing or invalid.
    """
    versions = {unit_id: unit.version for unit_id, unit in units.items()}
    versions.update(_validated_planned_versions(version_plan))
    return versions


def collect_npm_unit_ids(
    *,
    version_plan: dict[str, Any],
    units: dict[str, common.WorkspaceUnit],
) -> list[str]:
    """Return planned npm unit IDs in dependency order.

    Args:
        version_plan: Release-plan payload with unit/version changes.
        units: Workspace units keyed by unit ID.

    Returns:
        Ordered npm workspace unit IDs for publish preparation.

    Raises:
        ValueError: If the release plan references a missing workspace unit or
            contains invalid planned versions.
    """
    planned_versions = _validated_planned_versions(version_plan)
    npm_unit_ids: set[str] = set()
    for unit_id in planned_versions:
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
    """Create publish-ready npm directories with exact internal semver deps.

    Args:
        repo_root: Repository root used to resolve workspace members.
        version_plan: Release-plan payload with unit/version changes.
        units: Workspace units keyed by unit ID.
        registry_url: Target npm registry URL for publishConfig.
        output_dir: Directory where prepared publish artifacts are written.

    Returns:
        Report payload describing prepared npm publish artifacts.

    Raises:
        TypeError: If workspace metadata, version-plan payloads, or package
            dependency maps contain invalid JSON structure.
        ValueError: If workspace metadata, version planning, or package content
            is invalid for npm publication.
        OSError: If artifact directories cannot be created or copied.
    """
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

        target_dir = output_dir / Path(unit_id)
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
        package_data["files"] = ["dist"]

        publish_config = package_data.get("publishConfig", {})
        if not isinstance(publish_config, dict):
            raise TypeError(
                f"publishConfig in {unit.project_name} must be an object"
            )
        publish_config["registry"] = registry
        package_data["publishConfig"] = publish_config

        for field in DEPENDENCY_FIELDS:
            raw_dependencies = package_data.get(field)
            if raw_dependencies is None:
                continue
            if not isinstance(raw_dependencies, dict):
                raise TypeError(
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
        packed_file_names, tarball_path = _validate_packable_npm_artifact(
            target_dir
        )
        tarball_filename = tarball_path.name
        tarball_sha256 = hashlib.sha256(tarball_path.read_bytes()).hexdigest()
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
                "tarball_filename": tarball_filename,
                "tarball_sha256": tarball_sha256,
                "packed_files": packed_file_names,
            }
        )

    return {
        "schema_version": "1.0",
        "generated_at": common.iso_timestamp(),
        "registry_url": registry,
        "packages": packages,
    }


def validate_prepared_npm_package(package_json_path: Path) -> None:
    """Reject publish artifacts with remaining local-only dependency specs.

    Args:
        package_json_path: Path to the prepared package.json file to validate.

    Returns:
        None.

    Raises:
        TypeError: If dependency fields are not JSON objects.
        ValueError: If the prepared package metadata is malformed or still
            contains local-only dependency specifiers.
    """
    package_data = json.loads(package_json_path.read_text(encoding="utf-8"))
    for field in DEPENDENCY_FIELDS:
        raw_dependencies = package_data.get(field, {})
        if not isinstance(raw_dependencies, dict):
            raise TypeError(f"{package_json_path}: {field} must be an object")
        for dependency_name, dependency_version in raw_dependencies.items():
            if LOCAL_DEPENDENCY_SPEC_RE.match(str(dependency_version).strip()):
                raise ValueError(
                    f"{package_json_path}: dependency {dependency_name} "
                    "still uses a local-only specifier"
                )


def _validate_packable_npm_artifact(
    package_dir: Path,
) -> tuple[list[str], Path]:
    """Validate the prepared package with `npm pack --dry-run --json`.

    Args:
        package_dir: Prepared npm package directory.

    Returns:
        Ordered list of packed file paths from the validated dry-run result.

    Raises:
        RuntimeError: If `npm pack` fails.
        TypeError: If the npm JSON payload does not match the expected shape.
        ValueError: If the dry-run result is missing the tarball metadata or
            packed file list.
    """
    with tempfile.TemporaryDirectory(
        prefix="npm-pack-",
        dir=package_dir.parent,
    ) as temp_dir:
        npm_env = _build_npm_pack_environment(Path(temp_dir))
        dry_run_result = _run_npm_pack(
            package_dir,
            dry_run=True,
            env=npm_env,
        )
        packed_files = _extract_npm_packed_files(dry_run_result, package_dir)
        if not packed_files:
            raise ValueError(
                f"{package_dir}: npm pack dry-run produced no files"
            )
        if not any(
            packed_file == "dist" or packed_file.startswith("dist/")
            for packed_file in packed_files
        ):
            raise ValueError(
                f"{package_dir}: npm pack dry-run did not include any dist/ "
                "files"
            )

        pack_result = _run_npm_pack(
            package_dir,
            dry_run=False,
            env=npm_env,
        )
        dry_run_filename = _extract_npm_pack_filename(
            dry_run_result,
            package_dir,
        )
        pack_filename = _extract_npm_pack_filename(pack_result, package_dir)
        if dry_run_filename != pack_filename:
            raise ValueError(
                f"{package_dir}: npm pack filename changed between dry-run "
                f"and pack: {dry_run_filename} != {pack_filename}"
            )

        packed_files_from_pack = _extract_npm_packed_files(
            pack_result,
            package_dir,
        )
        if packed_files_from_pack and packed_files_from_pack != packed_files:
            raise ValueError(
                f"{package_dir}: npm pack file list changed between dry-run "
                "and pack"
            )

        filename = pack_filename
        tarball_path = package_dir / filename
        if not tarball_path.exists():
            raise ValueError(
                f"{package_dir}: npm pack did not create {filename}"
            )
        return packed_files, tarball_path


def _build_npm_pack_environment(temp_dir: Path) -> dict[str, str]:
    """Return an isolated npm environment rooted in a writable temp dir.

    Args:
        temp_dir: Writable temporary directory used to isolate npm state.

    Returns:
        Environment mapping with HOME, npm cache, npm userconfig, and XDG
        paths rooted under ``temp_dir``.
    """
    cache_dir = temp_dir / "cache"
    xdg_cache_dir = temp_dir / "xdg-cache"
    xdg_config_dir = temp_dir / "xdg-config"
    user_config_path = temp_dir / ".npmrc"

    cache_dir.mkdir(parents=True, exist_ok=True)
    xdg_cache_dir.mkdir(parents=True, exist_ok=True)
    xdg_config_dir.mkdir(parents=True, exist_ok=True)
    user_config_path.write_text("", encoding="utf-8")

    env = os.environ.copy()
    env["HOME"] = str(temp_dir)
    env["NPM_CONFIG_CACHE"] = str(cache_dir)
    env["NPM_CONFIG_USERCONFIG"] = str(user_config_path)
    env["XDG_CACHE_HOME"] = str(xdg_cache_dir)
    env["XDG_CONFIG_HOME"] = str(xdg_config_dir)
    return env


def _run_npm_pack(
    package_dir: Path,
    *,
    dry_run: bool,
    env: dict[str, str],
) -> list[dict[str, Any]]:
    """Run npm pack and return the decoded JSON payload."""
    args = ["npm", "pack", "--json"]
    if dry_run:
        args.insert(2, "--dry-run")
    result = subprocess.run(  # noqa: S603
        args,
        cwd=package_dir,
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"npm pack failed in {package_dir}: {stderr}")

    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{package_dir}: npm pack produced invalid JSON"
        ) from exc
    if not isinstance(payload, list):
        raise TypeError(f"{package_dir}: npm pack payload must be a JSON array")
    for item in payload:
        if not isinstance(item, dict):
            raise TypeError(
                f"{package_dir}: npm pack payload entries must be objects"
            )
    return payload


def _extract_npm_pack_filename(
    pack_result: list[dict[str, Any]],
    package_dir: Path,
) -> str:
    """Return the pack tarball filename from an npm JSON payload."""
    if not pack_result:
        raise ValueError(f"{package_dir}: npm pack produced no result objects")
    filename = str(pack_result[0].get("filename", "")).strip()
    if not filename:
        raise ValueError(f"{package_dir}: npm pack result missing filename")
    return filename


def _extract_npm_packed_files(
    pack_result: list[dict[str, Any]],
    package_dir: Path,
) -> list[str]:
    """Return packed file paths from an npm JSON payload."""
    if not pack_result:
        raise ValueError(f"{package_dir}: npm pack produced no result objects")
    raw_files = pack_result[0].get("files", [])
    if not isinstance(raw_files, list):
        raise TypeError(f"{package_dir}: npm pack result files must be a list")
    packed_files: list[str] = []
    for item in raw_files:
        if isinstance(item, str):
            packed_files.append(item)
            continue
        if not isinstance(item, dict):
            raise TypeError(
                f"{package_dir}: npm pack result files entries must be strings "
                "or objects"
            )
        path = str(item.get("path", "")).strip()
        if not path:
            raise ValueError(
                f"{package_dir}: npm pack result file entry missing path"
            )
        packed_files.append(path)
    return packed_files


def parse_args() -> argparse.Namespace:
    """Parse CLI options.

    Returns:
        Parsed CLI namespace for npm publish preparation.

    Raises:
        SystemExit: If CLI arguments are invalid.
    """
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
    """Prepare npm publish artifacts and write a report.

    Returns:
        Process exit status code.

    Raises:
        ValueError: If workspace or release-plan inputs are invalid.
        OSError: If prepared artifacts or reports cannot be written.
    """
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
