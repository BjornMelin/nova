#!/usr/bin/env python3
"""Generate committed Python SDK package sources from canonical OpenAPI."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from nova_runtime_support import (
    SDK_VISIBILITY_EXTENSION,
    SDK_VISIBILITY_INTERNAL,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_ROOT = REPO_ROOT / "packages" / "contracts" / "openapi"
GENERATOR_ROOT = REPO_ROOT / "scripts" / "release" / "openapi_python_client"
GENERATOR_CONFIG_PATH = GENERATOR_ROOT / "config.yaml"
GENERATOR_TEMPLATE_PATH = GENERATOR_ROOT / "templates"
_IGNORED_PARTS = {"__pycache__"}
_IGNORED_PREFIXES = (".",)
_GENERATOR_TIMEOUT_SECONDS = 60
_FORMATTER_TIMEOUT_SECONDS = 60
_HTTP_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
)


@dataclass(frozen=True)
class GenerationTarget:
    """Python SDK package synced from one committed OpenAPI document."""

    spec_path: Path
    output_path: Path
    package_name: str


TARGETS = (
    GenerationTarget(
        spec_path=OPENAPI_ROOT / "nova-file-api.openapi.json",
        output_path=(
            REPO_ROOT
            / "packages"
            / "nova_sdk_py_file"
            / "src"
            / "nova_sdk_py_file"
        ),
        package_name="nova_sdk_py_file",
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


def _load_spec_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"OpenAPI spec must decode to an object: {path}")
    return payload


def _filter_internal_operations_for_public_sdk(
    spec: dict[str, Any],
) -> dict[str, Any]:
    filtered = copy.deepcopy(spec)
    paths = filtered.get("paths")
    if not isinstance(paths, dict):
        raise TypeError("OpenAPI spec missing paths object")

    for path, path_item in list(paths.items()):
        if not isinstance(path_item, dict):
            continue
        for method, operation in list(path_item.items()):
            if method not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            if (
                operation.get(SDK_VISIBILITY_EXTENSION)
                == SDK_VISIBILITY_INTERNAL
            ):
                del path_item[method]
        if not any(method in _HTTP_METHODS for method in path_item):
            del paths[path]
    return filtered


def _collect_component_refs(node: object) -> set[tuple[str, str]]:
    refs: set[tuple[str, str]] = set()
    if isinstance(node, dict):
        node_mapping = cast("dict[str, object]", node)
        ref = node_mapping.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/"):
            _, _, section, name = ref.split("/", 3)
            refs.add((section, name))
        for value in node_mapping.values():
            refs.update(_collect_component_refs(value))
    elif isinstance(node, list):
        for item in node:
            refs.update(_collect_component_refs(item))
    return refs


def _collect_security_scheme_refs(spec: dict[str, Any]) -> set[tuple[str, str]]:
    refs: set[tuple[str, str]] = set()

    def _collect_from_security(value: object) -> None:
        if not isinstance(value, list):
            return
        for requirement in value:
            if not isinstance(requirement, dict):
                continue
            for scheme_name in requirement:
                if isinstance(scheme_name, str):
                    refs.add(("securitySchemes", scheme_name))

    _collect_from_security(spec.get("security"))
    for path_item in (spec.get("paths") or {}).values():
        if not isinstance(path_item, dict):
            continue
        _collect_from_security(path_item.get("security"))
        for method, operation in path_item.items():
            if method not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            _collect_from_security(operation.get("security"))
    return refs


def _prune_unreferenced_components(spec: dict[str, Any]) -> dict[str, Any]:
    components = spec.get("components")
    if not isinstance(components, dict):
        return spec

    without_components = copy.deepcopy(spec)
    without_components.pop("components", None)
    pending = list(_collect_component_refs(without_components))
    pending.extend(_collect_security_scheme_refs(spec))
    referenced: set[tuple[str, str]] = set()

    while pending:
        section, name = pending.pop()
        ref = (section, name)
        if ref in referenced:
            continue
        referenced.add(ref)
        section_values = components.get(section)
        if not isinstance(section_values, dict):
            continue
        component_value = section_values.get(name)
        if component_value is None:
            continue
        pending.extend(_collect_component_refs(component_value))

    pruned = copy.deepcopy(spec)
    pruned_components = pruned.get("components")
    if not isinstance(pruned_components, dict):
        return pruned

    for section, section_values in list(pruned_components.items()):
        if not isinstance(section_values, dict):
            continue
        if section == "securitySchemes":
            continue
        kept = {
            name: value
            for name, value in section_values.items()
            if (section, name) in referenced
        }
        if kept:
            pruned_components[section] = kept
        else:
            del pruned_components[section]

    if not pruned_components:
        pruned.pop("components", None)
    return pruned


def _write_temp_spec(*, spec: dict[str, Any], destination: Path) -> Path:
    destination.write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination


def _repair_job_record_result_parser(root: Path) -> None:
    path = root / "models" / "job_record.py"
    if not path.exists():
        return

    content = path.read_text(encoding="utf-8")
    old = (
        "                if not isinstance(data, dict):\n"
        "                    raise TypeError()\n"
        "                result_type_0 = "
        "JobRecordResultDetails.from_dict(data)\n"
    )
    new = (
        "                if not isinstance(data, Mapping):\n"
        "                    raise TypeError()\n"
        '                result_data = cast("Mapping[str, Any]", data)\n'
        "                result_type_0 = JobRecordResultDetails.from_dict(\n"
        "                    result_data\n"
        "                )\n\n"
    )
    if old not in content:
        if new in content:
            return
        raise RuntimeError(
            "expected JobRecord result parser snippet not found in "
            f"{path.relative_to(root)}"
        )

    path.write_text(content.replace(old, new), encoding="utf-8")


def _run_command(*, command: list[str], timeout: int, description: str) -> None:
    result = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{description} failed:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def _run_generated_ruff(root: Path) -> None:
    config_path = str(REPO_ROOT / "pyproject.toml")
    _run_command(
        command=[
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--config",
            config_path,
            "--fix-only",
            "--ignore",
            "D,E501",
            str(root),
        ],
        timeout=_FORMATTER_TIMEOUT_SECONDS,
        description=f"ruff check for {root}",
    )
    _run_command(
        command=[
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--config",
            config_path,
            str(root),
        ],
        timeout=_FORMATTER_TIMEOUT_SECONDS,
        description=f"ruff format for {root}",
    )


def _validate_generator_assets() -> None:
    for path in (GENERATOR_CONFIG_PATH, GENERATOR_TEMPLATE_PATH):
        if not path.exists():
            raise FileNotFoundError(f"required generator asset missing: {path}")


def _generate_target(target: GenerationTarget, temp_root: Path) -> Path:
    _validate_generator_assets()
    destination = temp_root / target.package_name
    filtered_spec = _prune_unreferenced_components(
        _filter_internal_operations_for_public_sdk(
            _load_spec_json(target.spec_path)
        )
    )
    spec_path = _write_temp_spec(
        spec=filtered_spec,
        destination=temp_root / f"{target.package_name}.openapi.json",
    )
    command = [
        sys.executable,
        "-m",
        "openapi_python_client",
        "generate",
        "--path",
        str(spec_path),
        "--config",
        str(GENERATOR_CONFIG_PATH),
        "--custom-template-path",
        str(GENERATOR_TEMPLATE_PATH),
        "--meta",
        "none",
        "--output-path",
        str(destination),
        "--overwrite",
        "--fail-on-warning",
    ]
    try:
        _run_command(
            command=command,
            timeout=_GENERATOR_TIMEOUT_SECONDS,
            description=(
                f"openapi-python-client generation for {target.spec_path}"
            ),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.decode(errors="replace")
            if isinstance(exc.stdout, bytes)
            else exc.stdout or ""
        )
        stderr = (
            exc.stderr.decode(errors="replace")
            if isinstance(exc.stderr, bytes)
            else exc.stderr or ""
        )
        raise RuntimeError(
            "openapi-python-client generation timed out for "
            f"{target.spec_path}:\nstdout:\n{stdout}\nstderr:\n{stderr}"
        ) from exc

    _repair_job_record_result_parser(destination)
    _run_generated_ruff(destination)
    return destination


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
