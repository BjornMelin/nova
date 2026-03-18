"""Tests for shared infra test helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from . import helpers


def test_load_repo_module_rolls_back_sys_modules_on_exec_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """load_repo_module must not leave partial imports behind."""
    module_path = tmp_path / "broken_module.py"
    module_path.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    monkeypatch.setattr(helpers, "REPO_ROOT", tmp_path)

    module_name = "tests.infra.broken_module"
    assert module_name not in sys.modules

    with pytest.raises(RuntimeError, match="boom"):
        helpers.load_repo_module(module_name, "broken_module.py")

    assert module_name not in sys.modules
