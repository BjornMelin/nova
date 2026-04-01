from __future__ import annotations

import ast
from pathlib import Path


def test_workflows_do_not_import_nova_file_api() -> None:
    package_root = Path(__file__).resolve().parents[1]
    scan_roots = [
        package_root / "src" / "nova_workflows",
        package_root / "tests",
    ]
    violations: list[str] = []

    for root in scan_roots:
        for path in root.rglob("*.py"):
            module = ast.parse(
                path.read_text(encoding="utf-8"),
                filename=str(path),
            )
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

    assert violations == []
