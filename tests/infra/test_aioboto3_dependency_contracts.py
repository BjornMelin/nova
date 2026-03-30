"""Contract tests for Nova's aioboto3 dependency and usage surface."""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_ROOT_LOCK = REPO_ROOT / "uv.lock"
_FILE_API_PYPROJECT = (
    REPO_ROOT / "packages" / "nova_file_api" / "pyproject.toml"
)
_DASH_BRIDGE_PYPROJECT = (
    REPO_ROOT / "packages" / "nova_dash_bridge" / "pyproject.toml"
)
_EXPECTED_AIOBOTO3_VERSION = "15.5.0"
_EXPECTED_AIOBOTOCORE_VERSION = "2.25.1"


def _dependency_strings(pyproject_path: Path) -> list[str]:
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    return list(payload["project"]["dependencies"])


def _lock_package_versions() -> dict[str, str]:
    payload = tomllib.loads(_ROOT_LOCK.read_text(encoding="utf-8"))
    return {
        package["name"]: package["version"]
        for package in payload["package"]
        if isinstance(package, dict)
        and isinstance(package.get("name"), str)
        and isinstance(package.get("version"), str)
    }


def test_runtime_packages_require_current_aioboto3_release_floor() -> None:
    """Runtime packages should require the current reviewed aioboto3 line."""
    file_api_dependencies = _dependency_strings(_FILE_API_PYPROJECT)
    dash_bridge_dependencies = _dependency_strings(_DASH_BRIDGE_PYPROJECT)
    expected_dependency = f"aioboto3>={_EXPECTED_AIOBOTO3_VERSION},<16"

    assert expected_dependency in file_api_dependencies
    assert expected_dependency in dash_bridge_dependencies


def test_uv_lock_resolves_upstream_supported_aioboto3_stack() -> None:
    """The lockfile should match the current supported async AWS stack."""
    versions = _lock_package_versions()

    assert versions["aioboto3"] == _EXPECTED_AIOBOTO3_VERSION
    assert versions["aiobotocore"] == _EXPECTED_AIOBOTOCORE_VERSION


def test_repo_uses_session_based_aioboto3_entrypoints_only() -> None:
    """Deprecated top-level aioboto3 entry helpers must stay absent."""
    violations: list[str] = []
    for path in REPO_ROOT.joinpath("packages").rglob("*.py"):
        if "/tests/" in path.as_posix():
            continue
        content = path.read_text(encoding="utf-8")
        if "aioboto3.client(" in content:
            violations.append(f"{path.relative_to(REPO_ROOT)} aioboto3.client")
        if "aioboto3.resource(" in content:
            violations.append(
                f"{path.relative_to(REPO_ROOT)} aioboto3.resource"
            )

    assert violations == []
