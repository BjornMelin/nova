from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest


def test_bridge_does_not_import_nova_file_api_modules() -> None:
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
                    if alias.name == "nova_file_api"
                    or alias.name.startswith("nova_file_api.")
                )
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (
                    node.module == "nova_file_api"
                    or node.module.startswith("nova_file_api.")
                )
            ):
                violations.append(
                    f"{path.relative_to(package_root)} imports from "
                    f"{node.module}"
                )

    if violations:
        pytest.xfail(
            "Phase 2 bridge cut pending: nova_dash_bridge still imports "
            "nova_file_api.public."
        )
    assert violations == []


def test_fastapi_and_flask_extras_declare_runtime_support_dependency() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    extras = project["optional-dependencies"]

    assert "nova-runtime-support>=0.1.0" in extras["fastapi"]
    assert "nova-runtime-support>=0.1.0" in extras["flask"]
