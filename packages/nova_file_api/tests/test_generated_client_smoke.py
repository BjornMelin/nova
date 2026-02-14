"""Generated OpenAPI client smoke tests."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from nova_file_api.app import create_app

_SUBPROCESS_TIMEOUT_SECONDS = 30


def test_generated_client_smoke(tmp_path: Path) -> None:
    """Generate a Python client from OpenAPI and compile generated files."""
    app = create_app()
    schema_path = tmp_path / "openapi.json"
    schema_path.write_text(
        json.dumps(app.openapi(), indent=2),
        encoding="utf-8",
    )
    output_path = tmp_path / "generated_client"

    if importlib.util.find_spec("openapi_python_client") is None:
        pytest.skip("openapi_python_client dependency is not installed")

    try:
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "openapi_python_client",
                "generate",
                "--path",
                str(schema_path),
                "--meta",
                "none",
                "--output-path",
                str(output_path),
                "--overwrite",
            ],
            check=False,
            text=True,
            capture_output=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            "openapi client generation timed out after "
            f"{_SUBPROCESS_TIMEOUT_SECONDS}s: {exc}"
        )
    assert generate.returncode == 0, (
        "openapi client generation failed:\n"
        f"stdout:\n{generate.stdout}\n"
        f"stderr:\n{generate.stderr}"
    )

    init_files = list(output_path.rglob("__init__.py"))
    assert init_files, "generated client package is missing __init__.py files"

    try:
        compile_result = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", str(output_path)],
            check=False,
            text=True,
            capture_output=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            "generated client compile smoke timed out after "
            f"{_SUBPROCESS_TIMEOUT_SECONDS}s: {exc}"
        )
    assert compile_result.returncode == 0, (
        "generated client compile smoke failed:\n"
        f"stdout:\n{compile_result.stdout}\n"
        f"stderr:\n{compile_result.stderr}"
    )
