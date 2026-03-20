"""Generated OpenAPI client smoke tests."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SUBPROCESS_TIMEOUT_SECONDS = 30
_REPO_ROOT = Path(__file__).resolve().parents[3]
_OPENAPI_ROOT = _REPO_ROOT / "packages" / "contracts" / "openapi"


def _generate_client_smoke(*, schema_path: Path, tmp_path: Path) -> None:
    if importlib.util.find_spec("openapi_python_client") is None:
        pytest.skip("openapi_python_client dependency is not installed")

    output_path = tmp_path / schema_path.stem

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


def test_file_openapi_generated_client_smoke(tmp_path: Path) -> None:
    """Generate a Python client from the canonical file API OpenAPI artifact."""
    _generate_client_smoke(
        schema_path=_OPENAPI_ROOT / "nova-file-api.openapi.json",
        tmp_path=tmp_path,
    )
