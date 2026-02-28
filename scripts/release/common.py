"""Shared helpers for release automation scripts."""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

BumpLevel = Literal["major", "minor", "patch"]
DEFAULT_MANIFEST_PATH = "docs/plan/release/RELEASE-VERSION-MANIFEST.md"


@dataclass(frozen=True)
class WorkspaceUnit:
    """Represents a versioned workspace unit in the monorepo."""

    unit_id: str
    path: Path
    project_name: str
    version: str
    dependencies: tuple[str, ...]


def iso_timestamp() -> str:
    """Return an RFC3339 UTC timestamp for artifacts."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def run_git(repo_root: Path, args: list[str]) -> str:
    """Run a git command and return stdout.

    Raises:
        RuntimeError: If git returns a non-zero status.
    """
    result = subprocess.run(
        ["git", *args],
        check=False,
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr}")
    return result.stdout.strip()


def load_workspace_units(repo_root: Path) -> dict[str, WorkspaceUnit]:
    """Load workspace units and metadata from pyproject.toml files."""
    root_pyproject = repo_root / "pyproject.toml"
    root_data = tomllib.loads(root_pyproject.read_text(encoding="utf-8"))
    members = (
        root_data.get("tool", {})
        .get("uv", {})
        .get("workspace", {})
        .get("members", [])
    )
    if not isinstance(members, list):
        raise ValueError("tool.uv.workspace.members must be a list")

    units: dict[str, WorkspaceUnit] = {}
    for member in members:
        if not isinstance(member, str):
            raise ValueError("workspace member paths must be strings")
        member_path = repo_root / member
        project_data = tomllib.loads(
            (member_path / "pyproject.toml").read_text(encoding="utf-8")
        ).get("project", {})
        name = str(project_data.get("name", "")).strip()
        version = str(project_data.get("version", "")).strip()
        dependencies = project_data.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise ValueError(f"project.dependencies in {member} must be a list")
        units[member] = WorkspaceUnit(
            unit_id=member,
            path=member_path,
            project_name=name,
            version=version,
            dependencies=tuple(str(dep) for dep in dependencies),
        )
    return units


def find_manifest_base_commit(
    repo_root: Path,
    manifest_path: str = DEFAULT_MANIFEST_PATH,
    refs: tuple[str, ...] = ("origin/main", "main", "HEAD"),
) -> str | None:
    """Return latest manifest-touching commit on main-like refs."""
    for ref in refs:
        try:
            run_git(repo_root, ["rev-parse", "--verify", ref])
        except RuntimeError:
            continue
        commit = run_git(
            repo_root,
            ["rev-list", "-n", "1", ref, "--", manifest_path],
        )
        if commit:
            return commit
    return None


def list_changed_files(
    repo_root: Path,
    *,
    head_commit: str,
    base_commit: str | None,
) -> list[str]:
    """List changed files for release planning."""
    if base_commit is None:
        output = run_git(
            repo_root,
            ["ls-tree", "-r", "--name-only", head_commit],
        )
    else:
        output = run_git(
            repo_root,
            ["diff", "--name-only", f"{base_commit}..{head_commit}"],
        )
    files = [line.strip() for line in output.splitlines() if line.strip()]
    return sorted(set(files))


def detect_changed_unit_ids(
    changed_files: list[str],
    units: dict[str, WorkspaceUnit],
) -> set[str]:
    """Return workspace unit IDs affected by changed files."""
    changed: set[str] = set()
    for path in changed_files:
        for unit_id in units:
            if path == unit_id or path.startswith(f"{unit_id}/"):
                changed.add(unit_id)
                break
    return changed


def collect_commit_messages(
    repo_root: Path,
    *,
    head_commit: str,
    base_commit: str | None,
) -> list[str]:
    """Collect commit subject/body text between baseline and head."""
    if base_commit is None:
        return []
    raw = run_git(
        repo_root,
        ["log", "--format=%s%n%b%n%x1e", f"{base_commit}..{head_commit}"],
    )
    messages = [part.strip() for part in raw.split("\x1e") if part.strip()]
    return messages


def determine_bump_level(messages: list[str]) -> BumpLevel:
    """Determine bump type from Conventional Commit-style messages."""
    for message in messages:
        if "BREAKING CHANGE" in message:
            return "major"
        header = message.splitlines()[0] if message.splitlines() else ""
        if re.match(r"^[a-zA-Z]+(\([^)]*\))?!:", header):
            return "major"

    for message in messages:
        header = message.splitlines()[0] if message.splitlines() else ""
        if re.match(r"^feat(\([^)]*\))?:", header):
            return "minor"

    return "patch"


def parse_dependency_name(spec: str) -> str:
    """Extract package name from a PEP 508-style dependency spec string."""
    token = spec.strip().strip('"').strip("'")
    if not token:
        return ""
    name = re.split(r"[\s\[<>=!~;]", token, maxsplit=1)[0]
    return name.strip()


def find_dependents(
    units: dict[str, WorkspaceUnit],
    changed_packages: set[str],
) -> set[str]:
    """Return unit IDs that depend on any changed package name."""
    dependents: set[str] = set()
    for unit_id, unit in units.items():
        dep_names = {parse_dependency_name(dep) for dep in unit.dependencies}
        if dep_names.intersection(changed_packages):
            dependents.add(unit_id)
    return dependents


def increment_semver(version: str, bump: BumpLevel) -> str:
    """Increment a semver string according to bump level."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version.strip())
    if not match:
        raise ValueError(f"Invalid semver: {version}")
    major, minor, patch = [int(part) for part in match.groups()]
    if bump == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def read_json(path: Path) -> dict:
    """Read a UTF-8 JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    """Write a JSON file with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
