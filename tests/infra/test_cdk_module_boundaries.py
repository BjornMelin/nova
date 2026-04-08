"""Boundary contracts for Nova CDK module ownership."""

from __future__ import annotations

import ast

from .helpers import read_repo_file


def _imports_runtime_stack(module_source: str) -> bool:
    """Return whether a module imports from ``.runtime_stack``."""
    tree = ast.parse(module_source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != "runtime_stack":
            continue
        if node.level == 1:
            return True
    return False


def test_release_support_stack_does_not_import_runtime_stack_privates() -> None:
    """Release-support stack imports shared authority modules only."""
    source = read_repo_file(
        "infra/nova_cdk/src/nova_cdk/release_support_stack.py"
    )
    assert not _imports_runtime_stack(source)


def test_release_control_stack_does_not_import_runtime_stack_privates() -> None:
    """Release-control stack imports shared authority modules only."""
    source = read_repo_file(
        "infra/nova_cdk/src/nova_cdk/release_control_stack.py"
    )
    assert not _imports_runtime_stack(source)
