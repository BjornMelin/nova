"""Contract tests for Nova's aioboto3 dependency and usage surface."""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_ROOT_LOCK = REPO_ROOT / "uv.lock"
_ROOT_PYPROJECT = REPO_ROOT / "pyproject.toml"
_FILE_API_PYPROJECT = (
    REPO_ROOT / "packages" / "nova_file_api" / "pyproject.toml"
)
_WORKFLOWS_PYPROJECT = (
    REPO_ROOT / "packages" / "nova_workflows" / "pyproject.toml"
)
_EXPECTED_AIOBOTO3_VERSION = "15.5.0"
_EXPECTED_AIOBOTOCORE_VERSION = "2.25.1"
_EXPECTED_BOTO3_VERSION = "1.40.61"
_EXPECTED_BOTOCORE_VERSION = "1.40.61"
_EXPECTED_BOTOCORE_SPEC = "botocore>=1.40.46,<1.40.62"
_EXPECTED_TYPES_AIOBOTOCORE_S3_SPEC = "types-aiobotocore-s3~=2.25.2"


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


def test_file_api_requires_current_aioboto3_release_floor() -> None:
    """The file API runtime keeps the reviewed aioboto3 dependency floor."""
    file_api_dependencies = _dependency_strings(_FILE_API_PYPROJECT)
    expected_dependency = f"aioboto3>={_EXPECTED_AIOBOTO3_VERSION},<16"

    assert expected_dependency in file_api_dependencies


def test_uv_lock_resolves_upstream_supported_aioboto3_stack() -> None:
    """The lockfile should match the current supported async AWS stack."""
    versions = _lock_package_versions()

    assert versions["aioboto3"] == _EXPECTED_AIOBOTO3_VERSION
    assert versions["aiobotocore"] == _EXPECTED_AIOBOTOCORE_VERSION
    assert versions["boto3"] == _EXPECTED_BOTO3_VERSION
    assert versions["botocore"] == _EXPECTED_BOTOCORE_VERSION


def test_workflows_require_supported_botocore_window() -> None:
    """Workflow botocore floor/cap must match aiobotocore's supported window."""
    workflow_dependencies = _dependency_strings(_WORKFLOWS_PYPROJECT)

    assert _EXPECTED_BOTOCORE_SPEC in workflow_dependencies


def test_root_dev_typing_stubs_match_reviewed_async_aws_stack() -> None:
    """Async boto typing stubs must stay on the current aiobotocore line."""
    payload = tomllib.loads(_ROOT_PYPROJECT.read_text(encoding="utf-8"))
    dev_dependencies = list(payload["dependency-groups"]["dev"])

    assert _EXPECTED_TYPES_AIOBOTOCORE_S3_SPEC in dev_dependencies


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
