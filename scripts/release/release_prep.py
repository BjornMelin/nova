"""Helpers for the canonical committed release prep artifact."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.release import common


def build_release_prep(
    *,
    prepared_from_commit: str,
    prepared_at: str,
    changed_report: dict[str, Any],
    version_plan: dict[str, Any],
) -> dict[str, Any]:
    """Return the canonical committed release prep payload."""
    return {
        "schema_version": "1.0",
        "prepared_at": prepared_at,
        "prepared_from_commit": prepared_from_commit,
        "base_commit": changed_report.get("base_commit"),
        "head_commit": changed_report.get("head_commit"),
        "first_release": changed_report.get("first_release", False),
        "changed_files": changed_report.get("changed_files", []),
        "changed_units": changed_report.get("changed_units", []),
        "global_bump": version_plan.get("global_bump"),
        "units": version_plan.get("units", []),
    }


def changed_report_from_release_prep(
    release_prep: dict[str, Any],
) -> dict[str, Any]:
    """Project the changed-units payload from a release prep object."""
    return {
        "schema_version": release_prep.get("schema_version", "1.0"),
        "generated_at": release_prep.get("prepared_at"),
        "base_commit": release_prep.get("base_commit"),
        "head_commit": release_prep.get("head_commit"),
        "first_release": release_prep.get("first_release", False),
        "changed_files": release_prep.get("changed_files", []),
        "changed_units": release_prep.get("changed_units", []),
    }


def version_plan_from_release_prep(
    release_prep: dict[str, Any],
) -> dict[str, Any]:
    """Project the version plan payload from a release prep object."""
    return {
        "schema_version": release_prep.get("schema_version", "1.0"),
        "generated_at": release_prep.get("prepared_at"),
        "base_commit": release_prep.get("base_commit"),
        "head_commit": release_prep.get("head_commit"),
        "global_bump": release_prep.get("global_bump"),
        "units": release_prep.get("units", []),
    }


def load_release_prep(path: str | Path) -> dict[str, Any]:
    """Load one release prep JSON object from disk."""
    return common.read_json(Path(path))
