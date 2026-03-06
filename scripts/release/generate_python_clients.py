#!/usr/bin/env python3
"""Generate committed Python SDK package sources from canonical OpenAPI."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_ROOT = REPO_ROOT / "packages" / "contracts" / "openapi"
_IGNORED_PARTS = {"__pycache__"}
_IGNORED_PREFIXES = (".",)
_GENERATOR_TIMEOUT_SECONDS = 60
_FORMATTER_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class GenerationTarget:
    """Python SDK package synced from one committed OpenAPI document."""

    spec_path: Path
    output_path: Path
    package_name: str


TARGETS = (
    GenerationTarget(
        spec_path=OPENAPI_ROOT / "nova-file-api.openapi.json",
        output_path=REPO_ROOT
        / "packages"
        / "nova_sdk_py_file"
        / "src"
        / "nova_sdk_py_file",
        package_name="nova_sdk_py_file",
    ),
    GenerationTarget(
        spec_path=OPENAPI_ROOT / "nova-auth-api.openapi.json",
        output_path=REPO_ROOT
        / "packages"
        / "nova_sdk_py_auth"
        / "src"
        / "nova_sdk_py_auth",
        package_name="nova_sdk_py_auth",
    ),
)


def _should_ignore(rel_path: Path) -> bool:
    return any(
        part in _IGNORED_PARTS or part.startswith(_IGNORED_PREFIXES)
        for part in rel_path.parts
    )


def _collect_file_map(root: Path) -> dict[Path, bytes]:
    file_map: dict[Path, bytes] = {}
    if not root.exists():
        return file_map

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_path = path.relative_to(root)
        if _should_ignore(rel_path):
            continue
        file_map[rel_path] = path.read_bytes()
    return file_map


def _remove_ignored_paths(root: Path) -> None:
    if not root.exists():
        return

    for path in sorted(root.rglob("*"), reverse=True):
        rel_path = path.relative_to(root)
        if not _should_ignore(rel_path):
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            continue
        path.unlink(missing_ok=True)


def _generate_target(target: GenerationTarget, temp_root: Path) -> Path:
    destination = temp_root / target.package_name
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "openapi_python_client",
            "generate",
            "--path",
            str(target.spec_path),
            "--meta",
            "none",
            "--output-path",
            str(destination),
            "--overwrite",
        ],
        check=False,
        text=True,
        capture_output=True,
        timeout=_GENERATOR_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "openapi-python-client generation failed for "
            f"{target.spec_path}:\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return destination


def _run_ruff(*, args: list[str], root: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ruff", *args, str(root)],
        check=False,
        text=True,
        capture_output=True,
        timeout=_FORMATTER_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "ruff step failed for "
            f"{root} ({' '.join(args)}):\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def _repair_missing_unset_imports(root: Path) -> None:
    for path in root.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if "Unset" not in content:
            continue
        updated = content.replace(
            "types import UNSET, Response",
            "types import UNSET, Response, Unset",
        )
        if updated != content:
            path.write_text(updated, encoding="utf-8")


def _normalize_generated_tree(root: Path) -> None:
    _repair_missing_unset_imports(root)
    _run_ruff(args=["check", "--select", "I", "--fix"], root=root)
    _run_ruff(args=["format"], root=root)


def _sync_generated_tree(source_root: Path, destination_root: Path) -> None:
    _remove_ignored_paths(destination_root)
    source_files = _collect_file_map(source_root)
    destination_files = _collect_file_map(destination_root)

    for rel_path in sorted(destination_files.keys() - source_files.keys()):
        (destination_root / rel_path).unlink()

    for rel_path, content in source_files.items():
        destination = destination_root / rel_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        current_content = (
            destination.read_bytes() if destination.exists() else None
        )
        if current_content != content:
            destination.write_bytes(content)

    for path in sorted(destination_root.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def _write_or_check(target: GenerationTarget, *, check: bool) -> list[str]:
    issues: list[str] = []
    with TemporaryDirectory() as temp_dir:
        generated_root = _generate_target(
            target=target,
            temp_root=Path(temp_dir),
        )
        _normalize_generated_tree(generated_root)
        generated_files = _collect_file_map(generated_root)
        current_files = _collect_file_map(target.output_path)

        if check:
            if generated_files != current_files:
                issues.append(
                    "stale generated python client artifact: "
                    f"{target.output_path}"
                )
            return issues

        target.output_path.mkdir(parents=True, exist_ok=True)
        _sync_generated_tree(generated_root, target.output_path)
    return issues


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for committed Python SDK generation."""
    parser = argparse.ArgumentParser(
        description="Generate committed Python SDKs from OpenAPI.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if committed Python SDK artifacts are stale.",
    )
    return parser.parse_args()


def main() -> int:
    """Generate committed Python SDK sources or fail on drift."""
    args = parse_args()
    issues: list[str] = []
    for target in TARGETS:
        issues.extend(_write_or_check(target, check=args.check))

    if issues:
        for issue in issues:
            print(issue)
        return 1

    message = (
        "generated python client artifacts are current"
        if args.check
        else "generated python client artifacts updated"
    )
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
