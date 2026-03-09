"""Tests for npm publish artifact preparation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.release import common, npm_publish


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_managed_package(
    path: Path,
    *,
    name: str,
    version: str,
    dependencies: dict[str, str] | None = None,
) -> None:
    dependency_block = json.dumps(dependencies or {}, indent=2)
    _write_text(
        path / "package.json",
        "{\n"
        f'  "name": "{name}",\n'
        '  "private": true,\n'
        f'  "version": "{version}",\n'
        '  "novaRelease": {"managed": true, "namespace": "nova"},\n'
        f'  "dependencies": {dependency_block},\n'
        '  "files": ["dist"],\n'
        '  "exports": {".": {"default": "./dist/index.js"}}\n'
        "}\n",
    )
    _write_text(path / "dist/index.js", "export const ready = true;\n")


def test_prepare_npm_publish_artifacts_rewrites_internal_versions(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_text(
        repo_root / "pyproject.toml",
        "[tool.uv]\n\n[tool.uv.workspace]\nmembers = []\n",
    )
    _write_text(
        repo_root / "package.json",
        "{\n"
        '  "private": true,\n'
        '  "workspaces": [\n'
        '    "packages/nova_sdk_fetch",\n'
        '    "packages/nova_sdk_file"\n'
        "  ]\n"
        "}\n",
    )
    _write_managed_package(
        repo_root / "packages/nova_sdk_fetch",
        name="@nova/sdk-fetch",
        version="0.1.0",
    )
    _write_managed_package(
        repo_root / "packages/nova_sdk_file",
        name="@nova/sdk-file",
        version="0.1.0",
        dependencies={"@nova/sdk-fetch": "file:../nova_sdk_fetch"},
    )

    units = common.load_workspace_units(repo_root)
    version_plan = {
        "units": [
            {
                "unit_id": "packages/nova_sdk_fetch",
                "new_version": "0.2.0",
            },
            {
                "unit_id": "packages/nova_sdk_file",
                "new_version": "0.2.0",
            },
        ]
    }

    report = npm_publish.prepare_npm_publish_artifacts(
        repo_root=repo_root,
        version_plan=version_plan,
        units=units,
        registry_url=(
            "https://cral-099060980393.d.codeartifact.us-east-1.amazonaws.com/npm/"
            "galaxypy-staging"
        ),
        output_dir=repo_root / ".artifacts/npm-publish",
    )

    assert [item["package"] for item in report["packages"]] == [
        "@nova/sdk-fetch",
        "@nova/sdk-file",
    ]
    assert report["registry_url"] == (
        "https://cral-099060980393.d.codeartifact.us-east-1.amazonaws.com/npm/"
        "galaxypy-staging/"
    )
    prepared_core_path = (
        repo_root / ".artifacts/npm-publish/packages/nova_sdk_file/package.json"
    )
    prepared_core = json.loads(prepared_core_path.read_text(encoding="utf-8"))
    assert prepared_core["version"] == "0.2.0"
    assert prepared_core["dependencies"]["@nova/sdk-fetch"] == "0.2.0"
    assert prepared_core["publishConfig"]["registry"] == (
        "https://cral-099060980393.d.codeartifact.us-east-1.amazonaws.com/npm/"
        "galaxypy-staging/"
    )
    assert "private" not in prepared_core
    assert "novaRelease" not in prepared_core


def test_planned_version_map_rejects_duplicate_unit_ids(
    tmp_path: Path,
) -> None:
    units = {
        "packages/nova_sdk_fetch": common.WorkspaceUnit(
            unit_id="packages/nova_sdk_fetch",
            path=tmp_path / "packages/nova_sdk_fetch",
            project_name="@nova/sdk-fetch",
            version="0.1.0",
            dependencies=(),
            package_format="npm",
            namespace="nova",
        )
    }

    with pytest.raises(ValueError, match="duplicate unit_id"):
        npm_publish.planned_version_map(
            version_plan={
                "units": [
                    {
                        "unit_id": "packages/nova_sdk_fetch",
                        "new_version": "0.2.0",
                    },
                    {
                        "unit_id": "packages/nova_sdk_fetch",
                        "new_version": "0.3.0",
                    },
                ]
            },
            units=units,
        )


def test_prepare_npm_publish_artifacts_uses_unique_workspace_paths(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_text(
        repo_root / "pyproject.toml",
        "[tool.uv]\n\n[tool.uv.workspace]\nmembers = []\n",
    )
    _write_text(
        repo_root / "package.json",
        "{\n"
        '  "private": true,\n'
        '  "workspaces": [\n'
        '    "packages/a/sdk",\n'
        '    "packages/b/sdk"\n'
        "  ]\n"
        "}\n",
    )
    _write_managed_package(
        repo_root / "packages/a/sdk",
        name="@nova/sdk-a",
        version="0.1.0",
    )
    _write_managed_package(
        repo_root / "packages/b/sdk",
        name="@nova/sdk-b",
        version="0.1.0",
    )

    units = common.load_workspace_units(repo_root)
    version_plan = {
        "units": [
            {"unit_id": "packages/a/sdk", "new_version": "0.2.0"},
            {"unit_id": "packages/b/sdk", "new_version": "0.2.0"},
        ]
    }

    report = npm_publish.prepare_npm_publish_artifacts(
        repo_root=repo_root,
        version_plan=version_plan,
        units=units,
        registry_url="https://registry.example.com",
        output_dir=repo_root / ".artifacts/npm-publish",
    )

    assert [item["publish_dir"] for item in report["packages"]] == [
        ".artifacts/npm-publish/packages/a/sdk",
        ".artifacts/npm-publish/packages/b/sdk",
    ]


def test_validate_prepared_npm_package_rejects_workspace_specs(
    tmp_path: Path,
) -> None:
    package_json = tmp_path / "package.json"
    package_json.write_text(
        "{\n"
        '  "name": "@nova/sdk-file",\n'
        '  "version": "0.1.0",\n'
        '  "dependencies": {"@nova/sdk-fetch": "file:../nova_sdk_fetch"}\n'
        "}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="local-only specifier"):
        npm_publish.validate_prepared_npm_package(package_json)


def test_planned_version_map_rejects_blank_new_version(
    tmp_path: Path,
) -> None:
    units = {
        "packages/nova_sdk_fetch": common.WorkspaceUnit(
            unit_id="packages/nova_sdk_fetch",
            path=tmp_path / "packages/nova_sdk_fetch",
            project_name="@nova/sdk-fetch",
            version="0.1.0",
            dependencies=(),
            package_format="npm",
            namespace="nova",
        )
    }

    with pytest.raises(ValueError, match="must declare new_version"):
        npm_publish.planned_version_map(
            version_plan={
                "units": [
                    {
                        "unit_id": "packages/nova_sdk_fetch",
                        "new_version": "",
                    }
                ]
            },
            units=units,
        )


def test_planned_version_map_rejects_invalid_semver(
    tmp_path: Path,
) -> None:
    units = {
        "packages/nova_sdk_fetch": common.WorkspaceUnit(
            unit_id="packages/nova_sdk_fetch",
            path=tmp_path / "packages/nova_sdk_fetch",
            project_name="@nova/sdk-fetch",
            version="0.1.0",
            dependencies=(),
            package_format="npm",
            namespace="nova",
        )
    }

    with pytest.raises(ValueError, match="invalid semver"):
        npm_publish.planned_version_map(
            version_plan={
                "units": [
                    {
                        "unit_id": "packages/nova_sdk_fetch",
                        "new_version": "latest",
                    }
                ]
            },
            units=units,
        )
