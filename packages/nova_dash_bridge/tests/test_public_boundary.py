from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import nova_dash_bridge

_FORBIDDEN_ROOT = "nova_file_api"
_FORBIDDEN_PREFIX = _FORBIDDEN_ROOT + "."


def test_bridge_has_no_runtime_package_imports() -> None:
    package_root = (
        Path(__file__).resolve().parents[1] / "src" / "nova_dash_bridge"
    )
    violations: list[str] = []

    for path in package_root.rglob("*.py"):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                violations.extend(
                    f"{path.relative_to(package_root)} imports {alias.name}"
                    for alias in node.names
                    if alias.name == _FORBIDDEN_ROOT
                    or alias.name.startswith(_FORBIDDEN_PREFIX)
                )
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (
                    node.module == _FORBIDDEN_ROOT
                    or node.module.startswith(_FORBIDDEN_PREFIX)
                )
            ):
                violations.append(
                    f"{path.relative_to(package_root)} imports from "
                    f"{node.module}"
                )

    assert violations == []


def test_browser_only_packaging_contract() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    dependencies = project.get("dependencies", [])
    extras = project.get("optional-dependencies", {})

    assert dependencies == []
    assert set(extras) == {"dash"}
    assert extras["dash"] == ["dash>=3.2.0,<5.0.0"]


def test_public_exports_are_browser_only() -> None:
    assert nova_dash_bridge.__all__ == [
        "FileTransferAssets",
        "S3FileUploader",
        "__version__",
    ]
    assert hasattr(nova_dash_bridge, "FileTransferAssets")
    assert hasattr(nova_dash_bridge, "S3FileUploader")
    assert not hasattr(nova_dash_bridge, "create_fastapi_app")
    assert not hasattr(nova_dash_bridge, "create_fastapi_router")
    assert not hasattr(nova_dash_bridge, "create_file_transfer_blueprint")
    assert not hasattr(nova_dash_bridge, "register_file_transfer_assets")
    assert not hasattr(nova_dash_bridge, "register_file_transfer_blueprint")
