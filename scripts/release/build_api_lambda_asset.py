"""Build the native zip-packaged Lambda release artifact.

The resulting archive contains the install-ready ``nova_file_api`` Lambda
runtime tree for release publication.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_PYTHON_PLATFORM = "aarch64-manylinux2014"
_PYTHON_VERSION = "3.13"


def _run(*args: str) -> None:
    """Run one subprocess command from the repository root."""
    subprocess.run(args, cwd=REPO_ROOT, check=True)


def _remove_pycache(*, output_dir: Path) -> None:
    """Drop transient Python cache directories from the Lambda asset."""
    for pycache_dir in output_dir.rglob("__pycache__"):
        shutil.rmtree(pycache_dir)


def _build_asset(*, output_dir: Path) -> None:
    """Build the Lambda zip asset into the provided output directory."""
    with tempfile.TemporaryDirectory(
        prefix="nova-file-api-lambda-build-"
    ) as temp_dir:
        temp_root = Path(temp_dir)
        requirements_path = temp_root / "requirements.txt"
        wheel_dir = temp_root / "dist"
        wheel_dir.mkdir(parents=True, exist_ok=True)

        _run(
            "uv",
            "export",
            "--frozen",
            "--package",
            "nova-file-api",
            "--no-default-groups",
            "--no-editable",
            "--no-emit-workspace",
            "--no-emit-project",
            "--output-file",
            str(requirements_path),
        )
        _run(
            "uv",
            "pip",
            "install",
            "--target",
            str(output_dir),
            "--python-version",
            _PYTHON_VERSION,
            "--python-platform",
            _PYTHON_PLATFORM,
            "--only-binary",
            ":all:",
            "--requirements",
            str(requirements_path),
            "--link-mode",
            "copy",
        )
        _run(
            "uv",
            "build",
            "--package",
            "nova-runtime-support",
            "--wheel",
            "--out-dir",
            str(wheel_dir),
        )
        _run(
            "uv",
            "build",
            "--package",
            "nova-file-api",
            "--wheel",
            "--out-dir",
            str(wheel_dir),
        )
        wheels = sorted(str(path) for path in wheel_dir.glob("*.whl"))
        _run(
            "uv",
            "pip",
            "install",
            "--target",
            str(output_dir),
            "--python-version",
            _PYTHON_VERSION,
            "--python-platform",
            _PYTHON_PLATFORM,
            "--no-deps",
            *wheels,
        )

    _remove_pycache(output_dir=output_dir)


def _write_zip_archive(*, source_dir: Path, output_zip: Path) -> None:
    """Write one zip archive from the built Lambda asset directory."""
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    output_zip.unlink(missing_ok=True)
    with zipfile.ZipFile(
        output_zip,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(source_dir))


def main() -> int:
    """Build the API Lambda zip artifact for release publication."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-zip", required=True)
    args = parser.parse_args()

    output_zip = Path(args.output_zip).resolve()
    with tempfile.TemporaryDirectory(
        prefix="nova-file-api-lambda-asset-"
    ) as temp_dir:
        output_dir = Path(temp_dir)
        _build_asset(output_dir=output_dir)
        _write_zip_archive(source_dir=output_dir, output_zip=output_zip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
