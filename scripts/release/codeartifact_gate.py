"""Validate and render CodeArtifact staged publish/promotion gate artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import common

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
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
    )


def _load_candidates(
    version_plan: dict[str, Any],
    units: dict[str, common.WorkspaceUnit],
) -> list[PromotionCandidate]:
    candidates: list[PromotionCandidate] = []
    for item in version_plan.get("units", []):
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
    """Validate release gate contracts and return gate report payload."""
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest_sha256 = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
    if expected_manifest_sha256 and expected_manifest_sha256 != manifest_sha256:
        raise GateError(
            "release manifest digest mismatch: "
            f"expected {expected_manifest_sha256}, got {manifest_sha256}"
        )

    changed_units = common.read_json(changed_units_path)
    version_plan = common.read_json(version_plan_path)
    units = common.load_workspace_units(repo_root)

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

    changed_count = len(changed_units.get("changed_units", []))
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
        "promotion_candidates": [
            candidate.__dict__ for candidate in candidates
        ],
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI args for gate validation artifact generation."""
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
    """Run release gate validation and write JSON output artifacts."""
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
    gate_out.parent.mkdir(parents=True, exist_ok=True)
    gate_out.write_text(
        json.dumps(gate_report, indent=2) + "\n", encoding="utf-8"
    )

    candidates_out = Path(args.promotion_candidates_out)
    if not candidates_out.is_absolute():
        candidates_out = repo_root / candidates_out
    candidates_out.parent.mkdir(parents=True, exist_ok=True)
    candidates_out.write_text(
        json.dumps(gate_report["promotion_candidates"], indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"gate report written: {gate_out}")
    print(f"promotion candidates written: {candidates_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
