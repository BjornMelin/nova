"""Build the shared zip-packaged workflow Lambda release artifact.

The resulting archive contains the install-ready ``nova_workflows`` Lambda
runtime tree used by all Step Functions task handlers.
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
    subprocess.run(args, cwd=REPO_ROOT, check=True)  # noqa: S603


def _remove_pycache(*, output_dir: Path) -> None:
    """Drop transient Python cache directories from the Lambda asset."""
    for pycache_dir in output_dir.rglob("__pycache__"):
        shutil.rmtree(pycache_dir)


def _build_asset(*, output_dir: Path) -> None:
    """Build the workflow Lambda zip asset into the provided directory."""
    with tempfile.TemporaryDirectory(
        prefix="nova-workflows-lambda-build-"
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
            "nova-workflows",
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
            "nova-workflows",
            "--wheel",
            "--out-dir",
            str(wheel_dir),
        )
        wheels = sorted(str(path) for path in wheel_dir.glob("*.whl"))
        if not wheels:
            raise RuntimeError(
                "No wheel artifacts were produced in "
                f"{wheel_dir} for output target {output_dir}"
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
            "--no-deps",
            *wheels,
        )

    _remove_pycache(output_dir=output_dir)


def _write_zip_archive(*, source_dir: Path, output_zip: Path) -> None:
    """Write one normalized zip archive from a built asset directory."""
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    output_zip.unlink(missing_ok=True)
    with zipfile.ZipFile(
        output_zip,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive_entry = zipfile.ZipInfo(
                    filename=path.relative_to(source_dir).as_posix(),
                    date_time=(1980, 1, 1, 0, 0, 0),
                )
                archive_entry.compress_type = zipfile.ZIP_DEFLATED
                archive_entry.external_attr = 0o100644 << 16
                archive.writestr(archive_entry, path.read_bytes())


def main() -> int:
    """Build the workflow Lambda zip artifact for release publication.

    Args:
        None.

    Returns:
        Process exit code where 0 means success.

    Raises:
        OSError: If temporary directory or output archive operations fail.
        subprocess.CalledProcessError:
            If underlying build/install commands fail.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-zip", required=True)
    args = parser.parse_args()

    output_zip = Path(args.output_zip).resolve()
    with tempfile.TemporaryDirectory(
        prefix="nova-workflows-lambda-asset-"
    ) as temp_dir:
        output_dir = Path(temp_dir)
        _build_asset(output_dir=output_dir)
        _write_zip_archive(source_dir=output_dir, output_zip=output_zip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
