from __future__ import annotations

import ast
from pathlib import Path

_ALLOWED_PREFIX = "nova_file_api.public"


def test_bridge_only_imports_public_nova_file_api_modules() -> None:
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
                    if (
                        alias.name == "nova_file_api"
                        or alias.name.startswith("nova_file_api.")
                    )
                    and not alias.name.startswith(_ALLOWED_PREFIX)
                )
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (
                    node.module == "nova_file_api"
                    or node.module.startswith("nova_file_api.")
                )
                and not node.module.startswith(_ALLOWED_PREFIX)
            ):
                violations.append(
                    f"{path.relative_to(package_root)} imports from "
                    f"{node.module}"
                )

    assert violations == []
