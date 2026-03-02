"""Validate and render CodeArtifact staged publish/promotion gate artifacts."""

from __future__ import annotations

import argparse
import hashlib
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from scripts.release import common

SEMVER_RE = re.compile(
    r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
MANIFEST_ROW_RE = re.compile(
    r"\|\s*`(?P<unit>[^`]+)`\s*\|\s*`(?P<package>[^`]+)`\s*\|"
    r"\s*`(?P<version>[^`]+)`\s*\|"
)


@dataclass(frozen=True)
class PromotionCandidate:
    """Package version candidate for staged→prod promotion."""

    format: str
    namespace: str | None
    package: str
    version: str
    unit_id: str | None = None


class GateError(ValueError):
    """Raised when release gate validation fails."""


def _read_manifest_versions(manifest_text: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    for match in MANIFEST_ROW_RE.finditer(manifest_text):
        versions[match.group("package")] = match.group("version")
    return versions


def _normalize_pypi_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def _validate_candidate(raw: dict[str, Any]) -> PromotionCandidate:
    package = str(raw.get("package", "")).strip()
    fmt = str(raw.get("format", "pypi")).strip().lower()
    namespace = raw.get("namespace")
    namespace_text = str(namespace).strip() if namespace is not None else None
    version = str(raw.get("version", "")).strip()
    item_unit_id = str(raw.get("unit_id", "")).strip() or None

    if not package:
        raise GateError("promotion candidate package must be non-empty")
    if fmt != "pypi":
        raise GateError(f"unsupported package format: {fmt}")
    if not SEMVER_RE.match(version):
        raise GateError(f"invalid semver version for {package}: {version}")
    if not _normalize_pypi_name(package).startswith("nova-"):
        raise GateError(
            "package "
            f"{package} violates internal namespace policy "
            "(must start with 'nova-')"
        )
    if namespace_text and namespace_text.lower() not in {
        "nova",
        "internal",
        "3m-cloud",
    }:
        raise GateError(
            f"namespace {namespace_text} is not allowed for package {package}"
        )

    return PromotionCandidate(
        format=fmt,
        namespace=namespace_text,
        package=package,
        version=version,
        unit_id=item_unit_id,
    )


def _load_candidates(
    version_plan: dict[str, Any],
    units: dict[str, common.WorkspaceUnit],
) -> list[PromotionCandidate]:
    candidates: list[PromotionCandidate] = []
    for item in version_plan.get("units", []):
        if not isinstance(item, Mapping):
            raise GateError("version plan units must be objects")
        unit_id = str(item.get("unit_id", "")).strip()
        version = str(item.get("new_version", "")).strip()
        if not unit_id or not version:
            raise GateError(
                "version plan contains unit without unit_id/new_version"
            )
        if unit_id not in units:
            raise GateError(
                f"version plan unit not found in workspace: {unit_id}"
            )
        candidates.append(
            _validate_candidate(
                {
                    "format": "pypi",
                    "namespace": "nova",
                    "package": units[unit_id].project_name,
                    "version": version,
                    "unit_id": unit_id,
                }
            )
        )
    return candidates


def validate_release_gates(
    *,
    repo_root: Path,
    manifest_path: Path,
    changed_units_path: Path,
    version_plan_path: Path,
    expected_manifest_sha256: str | None,
) -> dict[str, Any]:
    """Validate release gate contracts and return a gate report payload.

    Args:
        repo_root:
            Repository root used to resolve workspace units and relative paths.
        manifest_path:
            Path to the release manifest checked against expected hashes
            and package version rows in the manifest.
        changed_units_path:
            JSON path containing changed unit metadata for the release.
        version_plan_path:
            JSON path containing planned unit/version data for the release.
        expected_manifest_sha256:
            Optional SHA256 digest expected for the manifest file.

    Returns:
        dict[str, Any]:
            Gate report payload with manifest metadata, counts, and promotion
            candidates.

    Raises:
        GateError:
            If any validation rule fails, including manifest drift, malformed
            input structure, or release mismatch.
        OSError:
            If files cannot be read from disk.
        ValueError:
            If JSON payloads cannot be decoded.
    """
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest_sha256 = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
    if (
        expected_manifest_sha256 is not None
        and expected_manifest_sha256 != manifest_sha256
    ):
        raise GateError(
            "release manifest digest mismatch: "
            f"expected {expected_manifest_sha256}, got {manifest_sha256}"
        )

    changed_units = common.read_json(changed_units_path)
    version_plan = common.read_json(version_plan_path)
    units = common.load_workspace_units(repo_root)

    changed_items = changed_units.get("changed_units")
    if not isinstance(changed_items, list):
        raise GateError("changed_units must contain a changed_units array")
    changed_unit_ids: set[str] = set()
    for item in changed_items:
        if not isinstance(item, Mapping):
            raise GateError("changed_units entries must be objects")
        unit_id = str(item.get("unit_id", "")).strip()
        if not unit_id:
            raise GateError("changed_units entries require unit_id")
        changed_unit_ids.add(unit_id)

    planned_items = version_plan.get("units", [])
    if not isinstance(planned_items, list):
        raise GateError("version_plan.units must be a JSON array")
    planned_unit_ids = set[str]()
    for item in planned_items:
        if not isinstance(item, Mapping):
            raise GateError("version plan units must be objects")
        unit_id = str(item.get("unit_id", "")).strip()
        if unit_id:
            planned_unit_ids.add(unit_id)
    planned_unit_ids.discard("")

    if planned_unit_ids != changed_unit_ids:
        planned_sorted = ", ".join(sorted(planned_unit_ids))
        changed_sorted = ", ".join(sorted(changed_unit_ids))
        raise GateError(
            "changed_units and version_plan.units must match exactly: "
            f"planned=[{planned_sorted}] changed=[{changed_sorted}]"
        )

    if "## Canonical Runtime Monorepo" not in manifest_text:
        raise GateError(
            "release manifest missing canonical runtime monorepo section"
        )
    if "Schema: 1.0" not in manifest_text:
        raise GateError("release manifest schema marker missing")

    manifest_versions = _read_manifest_versions(manifest_text)
    candidates = _load_candidates(version_plan, units)

    for candidate in candidates:
        manifest_version = manifest_versions.get(candidate.package)
        if manifest_version is None:
            raise GateError(
                "manifest missing package entry for planned release: "
                f"{candidate.package}"
            )
        if manifest_version != candidate.version:
            raise GateError(
                f"manifest/package version mismatch for {candidate.package}: "
                f"manifest={manifest_version} plan={candidate.version}"
            )

    changed_count = len(changed_unit_ids)
    try:
        manifest_rel = str(manifest_path.relative_to(repo_root))
    except ValueError:
        manifest_rel = str(manifest_path)
    return {
        "schema_version": "1.0",
        "manifest_path": manifest_rel,
        "manifest_sha256": manifest_sha256,
        "changed_units_count": changed_count,
        "planned_package_count": len(candidates),
        "promotion_candidates": [asdict(candidate) for candidate in candidates],
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for release gate validation.

    Args:
        None.

    Returns:
        argparse.Namespace:
            Parsed CLI arguments used to locate inputs and outputs.

    Raises:
        SystemExit:
            When required CLI arguments are missing or malformed.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--manifest-path", default=common.DEFAULT_MANIFEST_PATH)
    parser.add_argument("--changed-units", required=True)
    parser.add_argument("--version-plan", required=True)
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument("--gate-report-out", required=True)
    parser.add_argument("--promotion-candidates-out", required=True)
    return parser.parse_args()


def main() -> int:
    """Run the release gate validation workflow and persist artifacts.

    Args:
        None.

    Returns:
        int:
            Zero when validation succeeds and artifacts are written.

    Raises:
        GateError:
            When release gate checks fail.
        OSError:
            When artifact files cannot be written.
    """
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    manifest_path = Path(args.manifest_path)
    if not manifest_path.is_absolute():
        manifest_path = repo_root / manifest_path
    changed_units_path = Path(args.changed_units)
    if not changed_units_path.is_absolute():
        changed_units_path = repo_root / changed_units_path
    version_plan_path = Path(args.version_plan)
    if not version_plan_path.is_absolute():
        version_plan_path = repo_root / version_plan_path

    gate_report = validate_release_gates(
        repo_root=repo_root,
        manifest_path=manifest_path,
        changed_units_path=changed_units_path,
        version_plan_path=version_plan_path,
        expected_manifest_sha256=args.expected_manifest_sha256,
    )

    gate_out = Path(args.gate_report_out)
    if not gate_out.is_absolute():
        gate_out = repo_root / gate_out
    common.write_json(gate_out, gate_report)

    candidates_out = Path(args.promotion_candidates_out)
    if not candidates_out.is_absolute():
        candidates_out = repo_root / candidates_out
    common.write_json(candidates_out, gate_report["promotion_candidates"])

    print(f"gate report written: {gate_out}")
    print(f"promotion candidates written: {candidates_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
