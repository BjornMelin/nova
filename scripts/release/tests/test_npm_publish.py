"""Tests for npm publish artifact preparation."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

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


def _fake_npm_pack_run(
    *,
    calls: list[list[str]],
    tarball_bytes: bytes = b"tarball-bytes",
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def _run(
        args: list[str],
        *,
        cwd: Path | str | None = None,
        check: bool = False,
        capture_output: bool = False,
        text: bool = False,
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        del check, capture_output, text
        cwd_path = Path(cwd or ".")
        calls.append(list(args))
        package_data = json.loads(
            (cwd_path / "package.json").read_text(encoding="utf-8")
        )
        package_name = str(package_data["name"]).removeprefix("@")
        filename = (
            f"{package_name.replace('/', '-')}-{package_data['version']}.tgz"
        )
        packed_files = [
            {"path": "dist/index.js"},
            {"path": "package.json"},
        ]
        if "--dry-run" not in args:
            (cwd_path / filename).write_bytes(tarball_bytes)
        payload = [
            {
                "filename": filename,
                "files": packed_files,
            }
        ]
        return subprocess.CompletedProcess(
            args=list(args),
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    return _run


def test_prepare_npm_publish_artifacts_rewrites_internal_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
        '  "workspaces": ["packages/nova_sdk_core", "packages/nova_sdk_file"]\n'
        "}\n",
    )
    _write_managed_package(
        repo_root / "packages/nova_sdk_core",
        name="@nova/sdk-core",
        version="0.1.0",
    )
    _write_managed_package(
        repo_root / "packages/nova_sdk_file",
        name="@nova/sdk-file",
        version="0.1.0",
        dependencies={"@nova/sdk-core": "^0.1.0", "openapi-fetch": "^0.17.0"},
    )

    units = common.load_workspace_units(repo_root)
    npm_calls: list[list[str]] = []
    monkeypatch.setattr(
        cast(Any, npm_publish).subprocess,
        "run",
        _fake_npm_pack_run(calls=npm_calls),
    )
    version_plan = {
        "units": [
            {
                "unit_id": "packages/nova_sdk_core",
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
        "@nova/sdk-core",
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
    assert prepared_core["dependencies"]["@nova/sdk-core"] == "0.2.0"
    assert prepared_core["dependencies"]["openapi-fetch"] == "^0.17.0"
    assert prepared_core["publishConfig"]["registry"] == (
        "https://cral-099060980393.d.codeartifact.us-east-1.amazonaws.com/npm/"
        "galaxypy-staging/"
    )
    assert prepared_core["files"] == ["dist"]
    assert "private" not in prepared_core
    assert "novaRelease" not in prepared_core
    prepared_package = next(
        item
        for item in report["packages"]
        if item["package"] == "@nova/sdk-file"
    )
    assert prepared_package["tarball_filename"] == "nova-sdk-file-0.2.0.tgz"
    assert (
        prepared_package["tarball_sha256"]
        == hashlib.sha256(b"tarball-bytes").hexdigest()
    )
    assert prepared_package["packed_files"] == [
        "dist/index.js",
        "package.json",
    ]
    assert npm_calls == [
        ["npm", "pack", "--dry-run", "--json"],
        ["npm", "pack", "--json"],
        ["npm", "pack", "--dry-run", "--json"],
        ["npm", "pack", "--json"],
    ]


def test_planned_version_map_rejects_duplicate_unit_ids(
    tmp_path: Path,
) -> None:
    units = {
        "packages/nova_sdk_file": common.WorkspaceUnit(
            unit_id="packages/nova_sdk_file",
            path=tmp_path / "packages/nova_sdk_file",
            project_name="@nova/sdk-file",
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
                        "unit_id": "packages/nova_sdk_file",
                        "new_version": "0.2.0",
                    },
                    {
                        "unit_id": "packages/nova_sdk_file",
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
        '  "dependencies": {"openapi-fetch": "file:../vendor/openapi-fetch"}\n'
        "}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="local-only specifier"):
        npm_publish.validate_prepared_npm_package(package_json)


def test_planned_version_map_rejects_blank_new_version(
    tmp_path: Path,
) -> None:
    units = {
        "packages/nova_sdk_file": common.WorkspaceUnit(
            unit_id="packages/nova_sdk_file",
            path=tmp_path / "packages/nova_sdk_file",
            project_name="@nova/sdk-file",
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
                        "unit_id": "packages/nova_sdk_file",
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
        "packages/nova_sdk_file": common.WorkspaceUnit(
            unit_id="packages/nova_sdk_file",
            path=tmp_path / "packages/nova_sdk_file",
            project_name="@nova/sdk-file",
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
                        "unit_id": "packages/nova_sdk_file",
                        "new_version": "latest",
                    }
                ]
            },
            units=units,
        )


def test_validate_packable_npm_artifact_rejects_missing_dist_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_dir = tmp_path / "packages/nova_sdk_file"
    package_dir.mkdir(parents=True)
    _write_text(
        package_dir / "package.json",
        "{\n"
        '  "name": "@nova/sdk-file",\n'
        '  "version": "0.1.0",\n'
        '  "files": ["src"],\n'
        '  "exports": {".": {"default": "./src/index.js"}}\n'
        "}\n",
    )
    _write_text(package_dir / "src/index.js", "export const ready = true;\n")

    def fake_run(
        args: list[str],
        *,
        cwd: Path | str | None = None,
        check: bool = False,
        capture_output: bool = False,
        text: bool = False,
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        del check, capture_output, text
        cwd_path = Path(cwd or ".")
        filename = "nova-sdk-file-0.1.0.tgz"
        if "--dry-run" not in args:
            (cwd_path / filename).write_bytes(b"tarball")
        return subprocess.CompletedProcess(
            args=list(args),
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "filename": filename,
                        "files": [{"path": "src/index.js"}],
                    }
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(cast(Any, npm_publish).subprocess, "run", fake_run)

    with pytest.raises(ValueError, match="did not include any dist/ files"):
        npm_publish._validate_packable_npm_artifact(package_dir)
