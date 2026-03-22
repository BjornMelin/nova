"""Tests for shared release workspace helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.release import common


def test_load_workspace_units_includes_managed_workspace_units(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    (repo_root / "pyproject.toml").write_text(
        "[tool.uv]\n\n"
        "[tool.uv.workspace]\n"
        'members = ["packages/nova_file_api"]\n'
        "\n[tool.nova.release]\n"
        "\n[[tool.nova.release.units]]\n"
        'unit_id = "packages/nova_sdk_r_file"\n'
        'path = "packages/nova_sdk_r_file"\n'
        'project_name = "nova.sdk.r.file"\n'
        "dependencies = []\n"
        'format = "r"\n'
        'codeartifact_format = "generic"\n'
        'namespace = "nova"\n',
        encoding="utf-8",
    )
    (repo_root / "packages/nova_file_api").mkdir(parents=True)
    (repo_root / "packages/nova_file_api/pyproject.toml").write_text(
        "[project]\n"
        'name = "nova-file-api"\n'
        'version = "0.1.0"\n'
        "dependencies = []\n",
        encoding="utf-8",
    )
    (repo_root / "package.json").write_text(
        "{\n"
        '  "private": true,\n'
        '  "workspaces": [\n'
        '    "packages/nova_sdk_file",\n'
        '    "packages/contracts/typescript"\n'
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_root / "packages/nova_sdk_file").mkdir(parents=True)
    (repo_root / "packages/nova_sdk_file/package.json").write_text(
        "{\n"
        '  "name": "@nova/sdk-file",\n'
        '  "version": "0.1.0",\n'
        '  "novaRelease": {"managed": true, "namespace": "nova"},\n'
        '  "dependencies": {"openapi-fetch": "^0.17.0"}\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_root / "packages/contracts/typescript").mkdir(parents=True)
    (repo_root / "packages/contracts/typescript/package.json").write_text(
        "{\n"
        '  "name": "@nova/contracts-ts-conformance",\n'
        '  "version": "0.1.0",\n'
        '  "novaRelease": {"managed": false}\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_root / "packages/nova_sdk_r_file").mkdir(parents=True)
    (repo_root / "packages/nova_sdk_r_file/DESCRIPTION").write_text(
        "Package: nova.sdk.r.file\nVersion: 0.1.0\n",
        encoding="utf-8",
    )

    units = common.load_workspace_units(repo_root)

    assert set(units) == {
        "packages/nova_file_api",
        "packages/nova_sdk_file",
        "packages/nova_sdk_r_file",
    }
    assert units["packages/nova_sdk_file"].package_format == "npm"
    assert units["packages/nova_sdk_file"].namespace == "nova"
    assert units["packages/nova_sdk_file"].dependencies == ("openapi-fetch",)
    assert units["packages/nova_sdk_r_file"].package_format == "r"
    assert units["packages/nova_sdk_r_file"].codeartifact_format == "generic"
    assert units["packages/nova_sdk_r_file"].namespace == "nova"
    assert units["packages/nova_sdk_r_file"].version == "0.1.0"


def test_load_workspace_units_rejects_r_registry_versions(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    (repo_root / "pyproject.toml").write_text(
        "[tool.uv]\n\n"
        "[tool.uv.workspace]\n"
        "members = []\n"
        "\n[tool.nova.release]\n"
        "\n[[tool.nova.release.units]]\n"
        'unit_id = "packages/nova_sdk_r_file"\n'
        'path = "packages/nova_sdk_r_file"\n'
        'project_name = "nova.sdk.r.file"\n'
        'version = "0.1.0"\n'
        "dependencies = []\n"
        'format = "r"\n'
        'codeartifact_format = "generic"\n'
        'namespace = "nova"\n',
        encoding="utf-8",
    )
    (repo_root / "packages/nova_sdk_r_file").mkdir(parents=True)
    (repo_root / "packages/nova_sdk_r_file/DESCRIPTION").write_text(
        "Package: nova.sdk.r.file\nVersion: 0.1.0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must not define version"):
        common.load_workspace_units(repo_root)


def test_load_workspace_units_rejects_r_unit_id_path_mismatch(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    (repo_root / "pyproject.toml").write_text(
        "[tool.uv]\n\n"
        "[tool.uv.workspace]\n"
        "members = []\n"
        "\n[tool.nova.release]\n"
        "\n[[tool.nova.release.units]]\n"
        'unit_id = "packages/nova_sdk_r_file"\n'
        'path = "packages/nova_sdk_r_file_renamed"\n'
        'project_name = "nova.sdk.r.file"\n'
        "dependencies = []\n"
        'format = "r"\n'
        'codeartifact_format = "generic"\n'
        'namespace = "nova"\n',
        encoding="utf-8",
    )
    (repo_root / "packages/nova_sdk_r_file_renamed").mkdir(parents=True)
    (repo_root / "packages/nova_sdk_r_file_renamed/DESCRIPTION").write_text(
        "Package: nova.sdk.r.file\nVersion: 0.1.0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must keep unit_id equal to path"):
        common.load_workspace_units(repo_root)


def test_load_workspace_units_rejects_unscoped_managed_npm_packages(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    (repo_root / "pyproject.toml").write_text(
        "[tool.uv]\n\n[tool.uv.workspace]\nmembers = []\n",
        encoding="utf-8",
    )
    (repo_root / "package.json").write_text(
        '{\n  "private": true,\n  "workspaces": ["packages/sdk"]\n}\n',
        encoding="utf-8",
    )
    (repo_root / "packages/sdk").mkdir(parents=True)
    (repo_root / "packages/sdk/package.json").write_text(
        "{\n"
        '  "name": "nova-sdk",\n'
        '  "version": "0.1.0",\n'
        '  "novaRelease": {"managed": true}\n'
        "}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires a scoped package"):
        common.load_workspace_units(repo_root)


def test_order_units_for_release_respects_internal_dependencies() -> None:
    units = {
        "packages/nova_dep": common.WorkspaceUnit(
            unit_id="packages/nova_dep",
            path=Path("packages/nova_dep"),
            project_name="@nova/dep",
            version="0.1.0",
            dependencies=(),
            package_format="npm",
            namespace="nova",
        ),
        "packages/nova_sdk_file": common.WorkspaceUnit(
            unit_id="packages/nova_sdk_file",
            path=Path("packages/nova_sdk_file"),
            project_name="@nova/sdk-file",
            version="0.1.0",
            dependencies=("packages/nova_dep",),
            package_format="npm",
            namespace="nova",
        ),
    }

    ordered = common.order_units_for_release(
        units,
        {"packages/nova_dep", "packages/nova_sdk_file"},
    )

    assert ordered == ["packages/nova_dep", "packages/nova_sdk_file"]
