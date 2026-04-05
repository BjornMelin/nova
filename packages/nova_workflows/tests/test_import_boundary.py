from __future__ import annotations

import ast
from pathlib import Path


def test_workflows_do_not_cross_api_boundary() -> None:
    package_root = Path(__file__).resolve().parents[1]
    scan_roots = [
        package_root / "src" / "nova_workflows",
        package_root / "tests",
    ]
    target_module = "nova_" + "file_api"
    target_prefix = f"{target_module}."
    allowed_modules = {
        "nova_file_api.export_models",
        "nova_file_api.workflow_facade",
    }
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
                        if (
                            alias.name == target_module
                            or (
                                alias.name.startswith(target_prefix)
                                and alias.name not in allowed_modules
                            )
                        )
                    )
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module is not None
                    and (
                        node.module == target_module
                        or (
                            node.module.startswith(target_prefix)
                            and node.module not in allowed_modules
                        )
                    )
                ):
                    violations.append(
                        f"{path.relative_to(package_root)} imports from "
                        f"{node.module}"
                    )

    assert violations == []
