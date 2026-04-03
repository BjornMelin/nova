"""Validate and render CodeArtifact staged publish/promotion gate artifacts."""

from __future__ import annotations

import argparse
import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.release import common, release_prep

SEMVER_RE = re.compile(
    r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
MANIFEST_ROW_RE = re.compile(
    r"\|\s*`(?P<unit>[^`]+)`\s*\|\s*`(?P<package>[^`]+)`\s*\|"
    r"\s*`(?P<version>[^`]+)`\s*\|"
)
SHA256_RE = re.compile(r"^[A-Fa-f0-9]{64}$")
GENERIC_PACKAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,254}$")


@dataclass(frozen=True)
class PromotionCandidate:
    """Package version candidate for staged→prod promotion."""

    format: str
    codeartifact_format: str
    namespace: str | None
    package: str
    version: str
    unit_id: str | None = None
    tarball_sha256: str | None = None
    signature_sha256: str | None = None


class GateError(ValueError):
    """Raised when release gate validation fails."""


def _serialize_candidate(candidate: PromotionCandidate) -> dict[str, Any]:
    """Return the canonical JSON payload for a promotion candidate."""
    payload: dict[str, Any] = {
        "format": candidate.format,
        "codeartifact_format": candidate.codeartifact_format,
        "namespace": candidate.namespace,
        "package": candidate.package,
        "version": candidate.version,
        "unit_id": candidate.unit_id,
    }
    if candidate.format == "r":
        payload["tarball_sha256"] = candidate.tarball_sha256
        payload["signature_sha256"] = candidate.signature_sha256
    return payload


def _read_manifest_versions(manifest_text: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    for match in MANIFEST_ROW_RE.finditer(manifest_text):
        package = match.group("package")
        version = match.group("version")
        if package in versions:
            existing_version = versions[package]
            row_text = match.group(0).strip()
            raise GateError(
                "duplicate package row in release manifest: "
                f"package={package!r} "
                f"existing_version={existing_version!r} "
                f"duplicate_version={version!r} "
                f"row={row_text!r}"
            )
        versions[package] = version
    return versions


def _normalize_pypi_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def _validate_candidate(raw: dict[str, Any]) -> PromotionCandidate:
    package = str(raw.get("package", "")).strip()
    fmt = str(raw.get("format", "pypi")).strip().lower()
    codeartifact_format = (
        str(raw.get("codeartifact_format", fmt)).strip().lower()
    )
    namespace = raw.get("namespace")
    namespace_text = str(namespace).strip() if namespace is not None else None
    version = str(raw.get("version", "")).strip()
    item_unit_id = str(raw.get("unit_id", "")).strip() or None
    raw_tarball_sha256 = raw.get("tarball_sha256")
    raw_signature_sha256 = raw.get("signature_sha256")
    tarball_sha256 = (
        str(raw_tarball_sha256).strip().lower() or None
        if raw_tarball_sha256 is not None
        else None
    )
    signature_sha256 = (
        str(raw_signature_sha256).strip().lower() or None
        if raw_signature_sha256 is not None
        else None
    )

    if not package:
        raise GateError("promotion candidate package must be non-empty")
    if fmt not in {"pypi", "npm", "r"}:
        raise GateError(f"unsupported package format: {fmt}")
    if codeartifact_format not in {"pypi", "npm", "generic"}:
        raise GateError(
            f"unsupported CodeArtifact package format: {codeartifact_format}"
        )
    if not SEMVER_RE.match(version):
        raise GateError(f"invalid semver version for {package}: {version}")
    if fmt == "pypi":
        if codeartifact_format != "pypi":
            raise GateError(
                "pypi release candidates must use CodeArtifact format pypi"
            )
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
                "namespace "
                f"{namespace_text} is not allowed for package {package}"
            )
    elif fmt == "npm":
        if codeartifact_format != "npm":
            raise GateError(
                "npm release candidates must use CodeArtifact format npm"
            )
        if not namespace_text:
            raise GateError(f"npm package {package} requires a namespace")
        expected_prefix = f"@{namespace_text}/"
        if not package.startswith(expected_prefix):
            raise GateError(
                f"npm package {package} must use scope {expected_prefix}"
            )
    else:
        if codeartifact_format != "generic":
            raise GateError(
                "R release candidates must use CodeArtifact format generic"
            )
        if namespace_text != "nova":
            raise GateError(
                f"generic package {package} must use namespace 'nova'"
            )
        if not GENERIC_PACKAGE_RE.match(package):
            raise GateError(
                "generic package name must use lowercase letters, digits, "
                f"dot, hyphen, or underscore: {package}"
            )
        if tarball_sha256 is None or signature_sha256 is None:
            raise GateError(
                "R release candidates require signed tarball evidence"
            )
        if not SHA256_RE.match(tarball_sha256):
            raise GateError(
                f"invalid tarball sha256 for R release candidate {package}"
            )
        if not SHA256_RE.match(signature_sha256):
            raise GateError(
                f"invalid signature sha256 for R release candidate {package}"
            )

    return PromotionCandidate(
        format=fmt,
        codeartifact_format=codeartifact_format,
        namespace=namespace_text,
        package=package,
        version=version,
        unit_id=item_unit_id,
        tarball_sha256=tarball_sha256,
        signature_sha256=signature_sha256,
    )


def _load_r_publish_report(
    r_publish_report_path: Path | None,
    units: dict[str, common.WorkspaceUnit],
) -> dict[str, dict[str, str]]:
    if r_publish_report_path is None:
        return {}

    report = common.read_json(r_publish_report_path)
    if not isinstance(report, Mapping):
        raise GateError("R publish report must be an object")

    raw_packages = report.get("packages")
    if not isinstance(raw_packages, list):
        raise GateError("R publish report field 'packages' must be a list")

    evidence_by_unit_id: dict[str, dict[str, str]] = {}
    for item in raw_packages:
        if not isinstance(item, Mapping):
            raise GateError("R publish report package entries must be objects")
        unit_id = str(item.get("unit_id", "")).strip()
        package = str(item.get("package", "")).strip()
        version = str(item.get("version", "")).strip()
        tarball_sha256 = str(item.get("tarball_sha256", "")).strip().lower()
        signature_sha256 = str(item.get("signature_sha256", "")).strip().lower()
        if not unit_id:
            raise GateError("R publish report package entries require unit_id")
        if unit_id not in units:
            raise GateError(
                f"R publish report references unknown unit: {unit_id}"
            )
        unit = units[unit_id]
        namespace = str(item.get("namespace", "")).strip()
        if unit.package_format != "r":
            raise GateError(
                "R publish report may only contain R package evidence: "
                f"{unit_id}"
            )
        if not namespace:
            raise GateError(
                f"R publish report namespace missing for unit {unit_id}"
            )
        if namespace != unit.namespace:
            raise GateError(
                "R publish report namespace mismatch for "
                f"{unit_id}: report={namespace!r} "
                f"workspace={unit.namespace!r}"
            )
        if package != unit.project_name:
            raise GateError(
                "R publish report package mismatch for "
                f"{unit_id}: report={package!r} workspace={unit.project_name!r}"
            )
        if version != unit.version:
            raise GateError(
                "R publish report version mismatch for "
                f"{unit_id}: report={version!r} workspace={unit.version!r}"
            )
        tarball_path = str(item.get("tarball_path", "")).strip()
        signature_path = str(item.get("signature_path", "")).strip()
        if not tarball_path:
            raise GateError(
                f"R publish report missing tarball_path for {unit_id}"
            )
        if not signature_path:
            raise GateError(
                f"R publish report missing signature_path for {unit_id}"
            )
        if not tarball_path.endswith(f"{version}.tar.gz"):
            raise GateError(
                "R publish report tarball metadata version mismatch for "
                f"{unit_id}: package_version={version!r} path={tarball_path!r}"
            )
        if not signature_path.endswith(f"{version}.tar.gz.sig"):
            raise GateError(
                "R publish report signature metadata version mismatch for "
                f"{unit_id}: package_version={version!r} path="
                f"{signature_path!r}"
            )
        if not SHA256_RE.match(tarball_sha256):
            raise GateError(
                f"invalid tarball sha256 in R publish report for {unit_id}"
            )
        if not SHA256_RE.match(signature_sha256):
            raise GateError(
                f"invalid signature sha256 in R publish report for {unit_id}"
            )
        if unit_id in evidence_by_unit_id:
            raise GateError(f"duplicate unit_id in R publish report: {unit_id}")
        evidence_by_unit_id[unit_id] = {
            "version": version,
            "namespace": namespace,
            "tarball_sha256": tarball_sha256,
            "signature_sha256": signature_sha256,
            "tarball_path": tarball_path,
            "signature_path": signature_path,
        }

    return evidence_by_unit_id


def _load_candidates(
    version_plan: dict[str, Any],
    units: dict[str, common.WorkspaceUnit],
    r_publish_evidence: dict[str, dict[str, str]],
) -> list[PromotionCandidate]:
    if not isinstance(version_plan, dict):
        raise GateError("version plan must be an object")

    raw_units = version_plan.get("units")
    if not isinstance(raw_units, list):
        raise GateError("version plan field 'units' must be a list")

    candidates: list[PromotionCandidate] = []
    consumed_r_evidence: set[str] = set()
    for item in raw_units:
        if not isinstance(item, Mapping):
            raise GateError("each version plan unit entry must be an object")
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
        unit = units[unit_id]
        if version != unit.version:
            raise GateError(
                "version plan new_version mismatch for unit "
                f"{unit_id}: workspace={unit.version!r} "
                f"plan={version!r}"
            )
        item_format = item.get("format")
        if item_format is not None and item_format != unit.package_format:
            raise GateError(
                "version plan format mismatch for unit "
                f"{unit_id}: plan={item_format!r} "
                f"workspace={unit.package_format!r}"
            )
        item_codeartifact_format = item.get("codeartifact_format")
        expected_codeartifact_format = common.resolve_codeartifact_format(unit)
        if (
            item_codeartifact_format is not None
            and item_codeartifact_format != expected_codeartifact_format
        ):
            raise GateError(
                "version plan codeartifact format mismatch for unit "
                f"{unit_id}: plan={item_codeartifact_format!r} "
                f"workspace={expected_codeartifact_format!r}"
            )
        item_namespace = item.get("namespace")
        if item_namespace is not None and item_namespace != unit.namespace:
            raise GateError(
                "version plan namespace mismatch for unit "
                f"{unit_id}: plan={item_namespace!r} "
                f"workspace={unit.namespace!r}"
            )
        evidence = r_publish_evidence.get(unit_id, {})
        if unit.package_format == "r":
            if not evidence:
                raise GateError(
                    "R release candidates require signed tarball evidence"
                )
            evidence_version = evidence.get("version", "").strip()
            if evidence_version != unit.version:
                raise GateError(
                    "R publish report version mismatch for "
                    f"{unit_id}: evidence={evidence_version!r} "
                    f"workspace={unit.version!r}"
                )
            tarball_path = evidence.get("tarball_path", "").strip()
            signature_path = evidence.get("signature_path", "").strip()
            if not tarball_path or not signature_path:
                raise GateError(
                    "R publish report missing tarball/signature metadata for "
                    f"{unit_id}"
                )
            if not tarball_path.endswith(f"{unit.version}.tar.gz"):
                raise GateError(
                    "R publish evidence tarball metadata version mismatch for "
                    f"{unit_id}: version={unit.version!r} path={tarball_path!r}"
                )
            if not signature_path.endswith(f"{unit.version}.tar.gz.sig"):
                raise GateError(
                    "R publish evidence signature metadata mismatch for "
                    f"{unit_id}: version={unit.version!r} path="
                    f"{signature_path!r}"
                )
            consumed_r_evidence.add(unit_id)
        candidates.append(
            _validate_candidate(
                {
                    "format": unit.package_format,
                    "codeartifact_format": common.resolve_codeartifact_format(
                        unit
                    ),
                    "namespace": unit.namespace,
                    "package": unit.project_name,
                    "version": version,
                    "unit_id": unit_id,
                    "tarball_sha256": evidence.get("tarball_sha256"),
                    "signature_sha256": evidence.get("signature_sha256"),
                }
            )
        )
    unused_r_evidence = sorted(set(r_publish_evidence) - consumed_r_evidence)
    if unused_r_evidence:
        raise GateError(
            "R publish report contains evidence for unknown version-plan "
            f"units: {', '.join(unused_r_evidence)}"
        )
    return candidates


def validate_release_gates(
    *,
    repo_root: Path,
    manifest_path: Path,
    changed_units_path: Path,
    version_plan_path: Path,
    expected_manifest_sha256: str | None,
    r_publish_report_path: Path | None = None,
    release_prep_path: Path | None = None,
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
        r_publish_report_path:
            Optional JSON path containing R package evidence. Required when the
            version plan contains R release candidates.
        release_prep_path:
            Optional JSON path to the canonical committed release-prep artifact.

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
    if expected_manifest_sha256 is not None and not SHA256_RE.match(
        expected_manifest_sha256
    ):
        raise GateError(
            "expected manifest sha256 must be a 64-character hex digest"
        )
    if (
        expected_manifest_sha256 is not None
        and expected_manifest_sha256 != manifest_sha256
    ):
        raise GateError(
            "release manifest digest mismatch: "
            f"expected {expected_manifest_sha256}, got {manifest_sha256}"
        )

    if release_prep_path is not None:
        release_prep_payload = common.read_json(release_prep_path)
        changed_units = release_prep.changed_report_from_release_prep(
            release_prep_payload
        )
        version_plan = release_prep.version_plan_from_release_prep(
            release_prep_payload
        )
    else:
        changed_units = common.read_json(changed_units_path)
        version_plan = common.read_json(version_plan_path)
    units = common.load_workspace_units(repo_root)
    r_publish_evidence = _load_r_publish_report(r_publish_report_path, units)

    if not isinstance(changed_units, Mapping):
        raise GateError("changed_units must contain a changed_units array")
    if not isinstance(version_plan, dict):
        raise GateError("version plan must be an object")

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
        if unit_id in changed_unit_ids:
            raise GateError(f"duplicate changed_units unit_id: {unit_id}")
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
            if unit_id in planned_unit_ids:
                raise GateError(f"duplicate version plan unit_id: {unit_id}")
            planned_unit_ids.add(unit_id)

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
    candidates = _load_candidates(version_plan, units, r_publish_evidence)

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
        "promotion_candidates": [
            _serialize_candidate(candidate) for candidate in candidates
        ],
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI args for gate validation artifact generation.

    Returns:
        argparse.Namespace with:
            - repo_root: repository root path
            - manifest_path: release manifest path
            - release_prep_path: optional release prep artifact path
            - changed_units: changed-units artifact path
            - version_plan: version-plan artifact path
            - expected_manifest_sha256: optional manifest SHA256 check value
            - gate_report_out: output report path
            - promotion_candidates_out: output candidates path
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--manifest-path", default=common.DEFAULT_MANIFEST_PATH)
    parser.add_argument("--release-prep-path", default="")
    parser.add_argument("--changed-units", default="")
    parser.add_argument("--version-plan", default="")
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument("--r-publish-report")
    parser.add_argument("--gate-report-out", required=True)
    parser.add_argument("--promotion-candidates-out", required=True)
    return parser.parse_args()


def main() -> int:
    """Run release gate validation and write JSON output artifacts.

    Returns:
        int: Process exit code (0 on success).
    """
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    release_prep_arg = getattr(args, "release_prep_path", "")
    changed_units_arg = getattr(args, "changed_units", "")
    version_plan_arg = getattr(args, "version_plan", "")
    expected_manifest_sha256 = getattr(args, "expected_manifest_sha256", None)
    r_publish_report_arg = getattr(args, "r_publish_report", None)

    manifest_path = Path(args.manifest_path)
    if not manifest_path.is_absolute():
        manifest_path = repo_root / manifest_path
    release_prep_path: Path | None = None
    if release_prep_arg:
        release_prep_path = Path(release_prep_arg)
        if not release_prep_path.is_absolute():
            release_prep_path = repo_root / release_prep_path
    changed_units_path = Path(changed_units_arg) if changed_units_arg else None
    if changed_units_path is not None and not changed_units_path.is_absolute():
        changed_units_path = repo_root / changed_units_path
    version_plan_path = Path(version_plan_arg) if version_plan_arg else None
    if version_plan_path is not None and not version_plan_path.is_absolute():
        version_plan_path = repo_root / version_plan_path
    if release_prep_path is None and (
        changed_units_path is None or version_plan_path is None
    ):
        raise GateError(
            "provide release_prep_path or both changed_units and version_plan"
        )
    r_publish_report_path = (
        Path(r_publish_report_arg) if r_publish_report_arg else None
    )
    if (
        r_publish_report_path is not None
        and not r_publish_report_path.is_absolute()
    ):
        r_publish_report_path = repo_root / r_publish_report_path

    gate_report = validate_release_gates(
        repo_root=repo_root,
        manifest_path=manifest_path,
        changed_units_path=changed_units_path or Path(),
        version_plan_path=version_plan_path or Path(),
        expected_manifest_sha256=expected_manifest_sha256,
        r_publish_report_path=r_publish_report_path,
        release_prep_path=release_prep_path,
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
