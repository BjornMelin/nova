"""Shared helpers for release automation scripts."""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

BumpLevel = Literal["major", "minor", "patch"]
PackageFormat = Literal["pypi", "npm"]
DEFAULT_MANIFEST_PATH = "docs/plan/release/RELEASE-VERSION-MANIFEST.md"


@dataclass(frozen=True)
class WorkspaceUnit:
    """Represents a versioned workspace unit in the monorepo."""

    unit_id: str
    path: Path
    project_name: str
    version: str
    dependencies: tuple[str, ...]
    package_format: PackageFormat = "pypi"
    namespace: str | None = None


def iso_timestamp() -> str:
    """Return an RFC3339 UTC timestamp for artifacts.

    Returns:
        RFC3339 timestamp string in UTC with zeroed microseconds.
    """
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def run_git(repo_root: Path, args: list[str]) -> str:
    """Run a git command and return stdout.

    Args:
        repo_root: Repository root used as working directory.
        args: Git CLI arguments to execute.

    Returns:
        Captured stdout with trailing whitespace removed.

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
    """Load release-managed workspace units and metadata.

    Args:
        repo_root: Repository root containing workspace configuration.

    Returns:
        Mapping of workspace member path to workspace metadata.

    Raises:
        ValueError: If workspace metadata is malformed or
            required values are missing.
    """
    units = _load_python_workspace_units(repo_root)
    npm_units = _load_npm_workspace_units(repo_root)

    duplicate_unit_ids = sorted(set(units).intersection(npm_units))
    if duplicate_unit_ids:
        raise ValueError(
            "workspace unit IDs overlap across package managers: "
            + ", ".join(duplicate_unit_ids)
        )
    units.update(npm_units)
    return units


def _load_python_workspace_units(repo_root: Path) -> dict[str, WorkspaceUnit]:
    """Load uv workspace units and metadata from pyproject.toml files."""
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
        if not name:
            raise ValueError(f"project.name in {member} must be non-empty")
        if not version:
            raise ValueError(f"project.version in {member} must be non-empty")
        dependencies = project_data.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise ValueError(f"project.dependencies in {member} must be a list")
        units[member] = WorkspaceUnit(
            unit_id=member,
            path=member_path,
            project_name=name,
            version=version,
            dependencies=tuple(str(dep) for dep in dependencies),
            package_format="pypi",
        )
    return units


def _load_npm_workspace_units(repo_root: Path) -> dict[str, WorkspaceUnit]:
    """Load release-managed npm workspace units from package.json workspaces."""
    root_package = repo_root / "package.json"
    if not root_package.exists():
        return {}

    root_data = json.loads(root_package.read_text(encoding="utf-8"))
    raw_workspaces = root_data.get("workspaces", [])
    if isinstance(raw_workspaces, dict):
        raw_workspaces = raw_workspaces.get("packages", [])
    if not isinstance(raw_workspaces, list):
        raise ValueError("package.json workspaces must be a list")

    units: dict[str, WorkspaceUnit] = {}
    for member in raw_workspaces:
        if not isinstance(member, str):
            raise ValueError("package.json workspace entries must be strings")
        member_path = repo_root / member
        package_data = json.loads(
            (member_path / "package.json").read_text(encoding="utf-8")
        )
        release_data = package_data.get("novaRelease", {})
        if not isinstance(release_data, dict):
            raise ValueError(f"novaRelease in {member} must be an object")
        managed_raw = release_data.get("managed", False)
        if not isinstance(managed_raw, bool):
            raise ValueError(
                f"novaRelease.managed in {member} must be a boolean"
            )
        if not managed_raw:
            continue

        name = str(package_data.get("name", "")).strip()
        version = str(package_data.get("version", "")).strip()
        if not name:
            raise ValueError(f"package.json name in {member} must be non-empty")
        if not version:
            raise ValueError(
                f"package.json version in {member} must be non-empty"
            )

        inferred_namespace = _npm_namespace_from_name(name)
        configured_namespace = release_data.get("namespace")
        if configured_namespace is not None:
            configured_namespace = str(configured_namespace).strip() or None
        if inferred_namespace and configured_namespace not in {
            None,
            inferred_namespace,
        }:
            raise ValueError(
                f"novaRelease.namespace in {member} must match npm scope"
            )
        if configured_namespace and not inferred_namespace:
            raise ValueError(
                f"novaRelease.namespace in {member} requires a scoped package"
            )

        units[member] = WorkspaceUnit(
            unit_id=member,
            path=member_path,
            project_name=name,
            version=version,
            dependencies=_collect_npm_dependency_names(package_data),
            package_format="npm",
            namespace=inferred_namespace or configured_namespace,
        )
    return units


def _collect_npm_dependency_names(
    package_data: dict[str, Any],
) -> tuple[str, ...]:
    """Return sorted dependency names from npm dependency maps."""
    dependency_names: set[str] = set()
    for field in (
        "dependencies",
        "optionalDependencies",
        "peerDependencies",
    ):
        raw_dependencies = package_data.get(field, {})
        if not isinstance(raw_dependencies, dict):
            raise ValueError(f"package.json field {field} must be an object")
        for name in raw_dependencies:
            dependency_names.add(str(name))
    return tuple(sorted(dependency_names))


def _npm_namespace_from_name(name: str) -> str | None:
    """Return the npm namespace without @, if the package is scoped."""
    if not name.startswith("@") or "/" not in name:
        return None
    namespace, _separator, _package = name[1:].partition("/")
    return namespace or None


def find_manifest_base_commit(
    repo_root: Path,
    manifest_path: str = DEFAULT_MANIFEST_PATH,
    refs: tuple[str, ...] = ("origin/main", "main", "HEAD"),
) -> str | None:
    """Return latest manifest commit reachable from the checked-out HEAD.

    Args:
        repo_root: Repository root containing git history.
        manifest_path: Repository-relative release manifest path.
        refs: Candidate refs to scan for latest manifest commit.

    Returns:
        Commit SHA for the latest manifest change that is an ancestor of HEAD,
        or None if no matching commit exists.
    """
    head_commit = run_git(repo_root, ["rev-parse", "--verify", "HEAD"])
    for ref in refs:
        try:
            run_git(repo_root, ["rev-parse", "--verify", ref])
        except RuntimeError:
            continue
        commit = run_git(
            repo_root,
            ["rev-list", "-n", "1", ref, "--", manifest_path],
        )
        if not commit:
            continue
        is_ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, head_commit],
            check=False,
            cwd=repo_root,
            text=True,
            capture_output=True,
        )
        if is_ancestor.returncode == 0:
            return commit
    return None


def list_changed_files(
    repo_root: Path,
    *,
    head_commit: str,
    base_commit: str | None,
) -> list[str]:
    """List changed files for release planning.

    Args:
        repo_root: Repository root containing git history.
        head_commit: Target head commit for diff/list operations.
        base_commit: Optional baseline commit; if omitted,
            list full tree at head.

    Returns:
        Sorted unique file paths changed between base and head.
    """
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
    """Return workspace unit IDs affected by changed files.

    Args:
        changed_files: Repository-relative changed file paths.
        units: Workspace units keyed by unit ID.

    Returns:
        Set of unit IDs touched by any changed file.
    """
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
    """Collect commit subject/body text between baseline and head.

    Args:
        repo_root: Repository root containing git history.
        head_commit: End of commit range.
        base_commit: Start of commit range, excluded.

    Returns:
        Commit messages in chronological git log output order.
    """
    if base_commit is None:
        return []
    raw = run_git(
        repo_root,
        ["log", "--format=%s%n%b%n%x1e", f"{base_commit}..{head_commit}"],
    )
    messages = [part.strip() for part in raw.split("\x1e") if part.strip()]
    return messages


def determine_bump_level(messages: list[str]) -> BumpLevel:
    """Determine bump type from Conventional Commit-style messages.

    Args:
        messages: Commit messages to inspect.

    Returns:
        Semver bump level inferred from conventional commit markers.
    """
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


def _normalize_package_name(name: str) -> str:
    """Normalize package names for reliable comparisons.

    Args:
        name: Raw package name.

    Returns:
        Lowercased package name normalized per PEP 503 conventions.
    """
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def parse_dependency_name(spec: str) -> str:
    """Extract package name from a PEP 508-style dependency spec string.

    Args:
        spec: Dependency spec string.

    Returns:
        Normalized dependency package name, or an empty string.
    """
    token = spec.strip().strip('"').strip("'")
    if not token:
        return ""
    name = re.split(r"[\s\[<>=!~;]", token, maxsplit=1)[0]
    return _normalize_package_name(name)


def find_dependents(
    units: dict[str, WorkspaceUnit],
    changed_packages: set[str],
) -> set[str]:
    """Return unit IDs that depend on any changed package name.

    Args:
        units: Workspace units keyed by unit ID.
        changed_packages: Package names that changed and may affect dependents.

    Returns:
        Unit IDs with at least one dependency in the changed package set.
    """
    normalized_changed = {
        _normalize_package_name(package) for package in changed_packages
    }
    dependents: set[str] = set()
    for unit_id, unit in units.items():
        dep_names = {parse_dependency_name(dep) for dep in unit.dependencies}
        if dep_names.intersection(normalized_changed):
            dependents.add(unit_id)
    return dependents


def order_units_for_release(
    units: dict[str, WorkspaceUnit],
    unit_ids: set[str] | list[str] | tuple[str, ...],
) -> list[str]:
    """Return release units in dependency order.

    Args:
        units: Workspace units keyed by unit ID.
        unit_ids: Unit IDs that should be ordered for build/publish work.

    Returns:
        Stable topological order where dependencies appear before dependents.

    Raises:
        KeyError: If any requested unit is missing from ``units``.
        ValueError: If dependency cycles are detected.
    """
    requested_ids = sorted(set(unit_ids))
    missing = sorted(set(requested_ids) - set(units))
    if missing:
        raise KeyError(
            "release ordering references unknown units: " + ", ".join(missing)
        )

    package_to_unit = {
        _normalize_package_name(units[unit_id].project_name): unit_id
        for unit_id in requested_ids
    }
    dependency_graph: dict[str, set[str]] = {
        unit_id: set() for unit_id in requested_ids
    }
    reverse_graph: dict[str, set[str]] = {
        unit_id: set() for unit_id in requested_ids
    }
    indegree = {unit_id: 0 for unit_id in requested_ids}

    for unit_id in requested_ids:
        internal_dependencies = {
            package_to_unit[dependency_name]
            for dep in units[unit_id].dependencies
            if (dependency_name := parse_dependency_name(dep))
            in package_to_unit
            and package_to_unit[dependency_name] != unit_id
        }
        dependency_graph[unit_id] = internal_dependencies
        indegree[unit_id] = len(internal_dependencies)
        for dependency_id in internal_dependencies:
            reverse_graph[dependency_id].add(unit_id)

    ready = sorted(
        unit_id
        for unit_id, dependency_count in indegree.items()
        if dependency_count == 0
    )
    ordered: list[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for dependent in sorted(reverse_graph[current]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
        ready.sort()

    if len(ordered) != len(requested_ids):
        raise ValueError(
            "release unit dependency graph contains a cycle: "
            + ", ".join(requested_ids)
        )
    return ordered


def increment_semver(version: str, bump: BumpLevel) -> str:
    """Increment a semver string according to bump level.

    Args:
        version: Input semantic version in MAJOR.MINOR.PATCH form.
        bump: Requested increment type.

    Returns:
        Incremented semantic version string.

    Raises:
        ValueError: If version is not a valid MAJOR.MINOR.PATCH string.
    """
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


def read_json(path: Path) -> dict[str, Any]:
    """Read a UTF-8 JSON file.

    Args:
        path: JSON file path.

    Returns:
        Parsed JSON object.

    Raises:
        TypeError:
            If the JSON root is not an object.
        json.JSONDecodeError:
            If `path.read_text()` contains malformed JSON.
        OSError:
            If `path.read_text()` cannot be read.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(
            f"JSON root must be an object, got {type(payload).__name__}"
        )
    return cast(dict[str, Any], payload)


def write_json(
    path: Path,
    payload: dict[str, Any] | list[Any] | str | int | bool | float | None,
) -> None:
    """Write a JSON file with stable formatting.

    Args:
        path: Destination JSON file path.
        payload: JSON-serializable object to persist.

    Returns:
        None:
            write_json(path, payload) returns None.

    Raises:
        OSError:
            If `path.parent.mkdir()` or `path.write_text()` fails.
        TypeError:
            If `payload` cannot be encoded as JSON.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
