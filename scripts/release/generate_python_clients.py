#!/usr/bin/env python3
"""Generate committed Python SDK package sources from canonical OpenAPI."""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import partial
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
        path_item_mapping = cast("dict[str, object]", path_item)
        for method, operation in list(path_item_mapping.items()):
            if method not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation_mapping = cast("dict[str, object]", operation)
            if (
                operation_mapping.get(SDK_VISIBILITY_EXTENSION)
                == SDK_VISIBILITY_INTERNAL
            ):
                del path_item_mapping[method]
        if not any(method in _HTTP_METHODS for method in path_item_mapping):
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
        r"(?s)        def _parse_result\("
        r".*?        result = _parse_result\(d.pop\(\"result\", UNSET\)\)\n"
    )
    new = (
        "        def _parse_result(\n"
        "            data: object,\n"
        "        ) -> JobRecordResultDetails | None | Unset:\n"
        "            if data is None:\n"
        "                return data\n"
        "            if isinstance(data, Unset):\n"
        "                return data\n"
        "            if not isinstance(data, Mapping):\n"
        "                raise TypeError(\n"
        '                    "Expected result payload to be a mapping or "\n'
        '                    "null"\n'
        "                )\n"
        '            result_data = cast("Mapping[str, Any]", data)\n'
        "            return JobRecordResultDetails.from_dict(result_data)\n"
        "\n"
        '        result = _parse_result(d.pop("result", UNSET))\n'
    )
    pattern = re.compile(old)
    updated, count = pattern.subn(new, content, count=1)
    if count == 0:
        if new in content:
            return
        raise RuntimeError(
            "expected JobRecord result parser snippet not found in "
            f"{path.relative_to(root)}"
        )

    path.write_text(updated, encoding="utf-8")


def _repair_export_resource_output_parser(root: Path) -> None:
    path = root / "models" / "export_resource.py"
    if not path.exists():
        return

    content = path.read_text(encoding="utf-8")
    old = (
        r"(?s)        def _parse_output\("
        r".*?        output = _parse_output\(d.pop\(\"output\", UNSET\)\)\n"
    )
    new = (
        "        def _parse_output(\n"
        "            data: object,\n"
        "        ) -> ExportOutput | None | Unset:\n"
        "            if data is None:\n"
        "                return data\n"
        "            if isinstance(data, Unset):\n"
        "                return data\n"
        "            if not isinstance(data, Mapping):\n"
        "                raise TypeError(\n"
        '                    "Expected output payload to be a mapping or "\n'
        '                    "null"\n'
        "                )\n"
        '            output_data = cast("Mapping[str, Any]", data)\n'
        "            return ExportOutput.from_dict(output_data)\n"
        "\n"
        '        output = _parse_output(d.pop("output", UNSET))\n'
    )
    pattern = re.compile(old)
    updated, count = pattern.subn(new, content, count=1)
    if count == 0:
        if new in content:
            return
        raise RuntimeError(
            "expected ExportResource output parser snippet not found in "
            f"{path.relative_to(root)}"
        )

    path.write_text(updated, encoding="utf-8")


_RELATIVE_IMPORT_RE = re.compile(
    r"^(\s*)from (\.+)([\w\.]*) import (.+)$", re.MULTILINE
)


def _rewrite_relative_imports(root: Path, package_name: str) -> None:
    def _absolute_module_name(path: Path, dot_count: int, suffix: str) -> str:
        package_segments = list(path.relative_to(root).parent.parts)
        levels_up = dot_count - 1
        if levels_up > 0:
            keep = max(0, len(package_segments) - levels_up)
            package_segments = package_segments[:keep]
        module_segments = package_segments + ([suffix] if suffix else [])
        if module_segments:
            return ".".join([package_name, *module_segments])
        return package_name

    def _replacement(path: Path, match: re.Match[str]) -> str:
        indent = match.group(1)
        dots = len(match.group(2))
        suffix = match.group(3)
        imported = match.group(4)
        absolute = _absolute_module_name(path, dots, suffix)
        return f"{indent}from {absolute} import {imported}"

    for path in root.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        new_content = _RELATIVE_IMPORT_RE.sub(
            partial(_replacement, path),
            content,
        )
        if new_content != content:
            path.write_text(new_content, encoding="utf-8")


def _repair_generated_python_package(root: Path, package_name: str) -> None:
    _rewrite_relative_imports(root, package_name)

    def _rewrite_file(
        relative_path: str,
        *,
        pattern: str,
        replacement: str,
        flags: int = 0,
        count: int = 1,
    ) -> None:
        path = root / relative_path
        if not path.exists():
            return
        content = path.read_text(encoding="utf-8")
        updated, replaced = re.subn(
            pattern,
            replacement,
            content,
            count=count,
            flags=flags,
        )
        if replaced and updated != content:
            path.write_text(updated, encoding="utf-8")

    simple_docs = {
        "models/job_record_payload.py": (
            "Additional job payload fields returned by the API."
        ),
        "models/job_event_data.py": (
            "Additional job event fields returned by the API."
        ),
        "models/enqueue_job_request_payload.py": (
            "Additional job payload fields included in enqueue requests."
        ),
        "models/error_body_details.py": (
            "Additional structured details returned with error payloads."
        ),
        "models/capability_descriptor_details.py": (
            "Additional capability descriptor fields returned by the API."
        ),
        "models/job_record_result_details.py": (
            "Additional job result details returned by the API."
        ),
    }
    for relative_path, docstring in simple_docs.items():
        _rewrite_file(
            relative_path,
            pattern=r'    """\s*"""',
            replacement=f'    """{docstring}"""',
        )

    _rewrite_file(
        "models/create_export_request.py",
        pattern=(
            r'^(?:"""Create-export request model for the public '
            r'Python SDK\."""\n\n)+'
            r"from __future__ import annotations\n\n"
        ),
        replacement=(
            '"""Create-export request model for the public Python SDK."""\n\n'
            "from __future__ import annotations\n\n"
        ),
        flags=re.MULTILINE,
    )
    _rewrite_file(
        "models/create_export_request.py",
        pattern=r"\Afrom __future__ import annotations\n\n",
        replacement=(
            '"""Create-export request model for the public Python SDK."""\n\n'
            "from __future__ import annotations\n\n"
        ),
    )
    _rewrite_file(
        "models/create_export_request.py",
        pattern=(
            r"class CreateExportRequest:\n"
            r'    """Request payload for export creation\.\n\n'
            r"    Attributes:\n"
            r"        filename \(str\):\n"
            r"        source_key \(str\):\n"
            r'    """\n'
        ),
        replacement=(
            "class CreateExportRequest:\n"
            '    """Request payload for creating an export.\n\n'
            "    Attributes:\n"
            "        filename (str): Client-facing filename to preserve in the "
            "export.\n"
            "        source_key (str): Storage key of the source object to "
            "export.\n"
            '    """\n'
        ),
        flags=re.MULTILINE,
    )
    _rewrite_file(
        "models/create_export_request.py",
        pattern=(
            r"    def to_dict\(self\) -> dict\[str, Any\]:\n"
            r"        filename = self\.filename\n"
        ),
        replacement=(
            "    def to_dict(self) -> dict[str, Any]:\n"
            '        """Serialize the request payload to a JSON-compatible '
            'mapping."""\n'
            "        filename = self.filename\n"
        ),
        flags=re.MULTILINE,
    )
    _rewrite_file(
        "models/create_export_request.py",
        pattern=(
            r"    def from_dict\(cls: type\[T\], "
            r"src_dict: Mapping\[str, Any\]\) -> T:\n"
            r"        d = dict\(src_dict\)\n"
        ),
        replacement=(
            "    def from_dict(cls: type[T], src_dict: Mapping[str, "
            "Any]) -> T:\n"
            '        """Deserialize the request payload from a '
            'JSON-compatible mapping."""\n'
            "        d = dict(src_dict)\n"
        ),
        flags=re.MULTILINE,
    )
    _rewrite_file(
        "models/export_output.py",
        pattern=(
            r'^(?:"""Export-output metadata model for the public '
            r'Python SDK\."""\n\n)+'
            r"from __future__ import annotations\n\n"
        ),
        replacement=(
            '"""Export-output metadata model for the public Python SDK."""\n\n'
            "from __future__ import annotations\n\n"
        ),
        flags=re.MULTILINE,
    )
    _rewrite_file(
        "models/export_output.py",
        pattern=r"\Afrom __future__ import annotations\n\n",
        replacement=(
            '"""Export-output metadata model for the public Python SDK."""\n\n'
            "from __future__ import annotations\n\n"
        ),
    )
    _rewrite_file(
        "models/export_output.py",
        pattern=(
            r"class ExportOutput:\n"
            r'    """Completed export output metadata\.\n\n'
            r"    Attributes:\n"
            r"        download_filename \(str\):\n"
            r"        key \(str\):\n"
            r'    """\n'
        ),
        replacement=(
            "class ExportOutput:\n"
            '    """Completed export output metadata.\n\n'
            "    Attributes:\n"
            "        download_filename (str): Filename presented to clients "
            "when downloading.\n"
            "        key (str): Storage key for the exported object.\n"
            '    """\n'
        ),
        flags=re.MULTILINE,
    )
    _rewrite_file(
        "models/export_output.py",
        pattern=(
            r"    def to_dict\(self\) -> dict\[str, Any\]:\n"
            r"        download_filename = self\.download_filename\n"
        ),
        replacement=(
            "    def to_dict(self) -> dict[str, Any]:\n"
            '        """Serialize the export output to a JSON-compatible '
            'mapping."""\n'
            "        download_filename = self.download_filename\n"
        ),
        flags=re.MULTILINE,
    )
    _rewrite_file(
        "models/export_output.py",
        pattern=(
            r"    def from_dict\(cls: type\[T\], "
            r"src_dict: Mapping\[str, Any\]\) -> T:\n"
            r"        d = dict\(src_dict\)\n"
        ),
        replacement=(
            "    def from_dict(cls: type[T], src_dict: Mapping[str, "
            "Any]) -> T:\n"
            '        """Deserialize the export output from a '
            'JSON-compatible mapping."""\n'
            "        d = dict(src_dict)\n"
        ),
        flags=re.MULTILINE,
    )

    _rewrite_file(
        "models/metrics_summary_response_activity.py",
        pattern=(
            r"        metrics_summary_response_activity = cls\(\)\n"
            r"\s*metrics_summary_response_activity\.additional_properties = d\n"
            r"\s*return metrics_summary_response_activity\n"
        ),
        replacement=(
            "        metrics_summary_response_activity = cls()\n"
            "        additional_properties: dict[str, int] = {}\n"
            "        for key, value in d.items():\n"
            "            if isinstance(value, bool):\n"
            "                raise TypeError(\n"
            '                    f"Invalid value for {key!r}: "\n'
            '                    "expected int, "\n'
            '                    "got bool"\n'
            "                )\n"
            "            additional_properties[key] = int(value)\n\n"
            "        metrics_summary_response_activity."
            "additional_properties = (\n"
            "            additional_properties\n"
            "        )\n"
            "        return metrics_summary_response_activity\n"
        ),
        flags=re.MULTILINE,
    )
    _rewrite_file(
        "models/metrics_summary_response_counters.py",
        pattern=(
            r"        metrics_summary_response_counters = cls\(\)\n"
            r"\s*metrics_summary_response_counters\.additional_properties = d\n"
            r"\s*return metrics_summary_response_counters\n"
        ),
        replacement=(
            "        metrics_summary_response_counters = cls()\n"
            "        additional_properties: dict[str, int] = {}\n"
            "        for key, value in d.items():\n"
            "            if isinstance(value, bool):\n"
            "                raise TypeError(\n"
            '                    f"Invalid value for {key!r}: "\n'
            '                    "expected int, "\n'
            '                    "got bool"\n'
            "                )\n"
            "            additional_properties[key] = int(value)\n\n"
            "        metrics_summary_response_counters."
            "additional_properties = (\n"
            "            additional_properties\n"
            "        )\n"
            "        return metrics_summary_response_counters\n"
        ),
        flags=re.MULTILINE,
    )
    _rewrite_file(
        "models/metrics_summary_response_latencies_ms.py",
        pattern=(
            r"        metrics_summary_response_latencies_ms = cls\(\)\n"
            r"\s*metrics_summary_response_latencies_ms."
            r"additional_properties = d\n"
            r"\s*return metrics_summary_response_latencies_ms\n"
        ),
        replacement=(
            "        metrics_summary_response_latencies_ms = cls()\n"
            "        additional_properties: dict[str, float] = {}\n"
            "        for key, value in d.items():\n"
            "            if isinstance(value, bool):\n"
            "                raise TypeError(\n"
            '                    f"Invalid value for {key!r}: "\n'
            '                    "expected float, "\n'
            '                    "got bool"\n'
            "                )\n"
            "            additional_properties[key] = float(value)\n\n"
            "        metrics_summary_response_latencies_ms."
            "additional_properties = (\n"
            "            additional_properties\n"
            "        )\n"
            "        return metrics_summary_response_latencies_ms\n"
        ),
        flags=re.MULTILINE,
    )
    _rewrite_file(
        "models/readiness_response_checks.py",
        pattern=(
            r"        readiness_response_checks = cls\(\)\n"
            r"\s*readiness_response_checks\.additional_properties = d\n"
            r"\s*return readiness_response_checks\n"
        ),
        replacement=(
            "        readiness_response_checks = cls()\n"
            "        additional_properties: dict[str, bool] = {}\n"
            "        for key, value in d.items():\n"
            "            if not isinstance(value, bool):\n"
            "                raise TypeError(\n"
            '                    f"Invalid value for {key!r}: "\n'
            '                    "expected bool, "\n'
            '                    f"got {type(value).__name__}"\n'
            "                )\n"
            "            additional_properties[key] = value\n\n"
            "        readiness_response_checks.additional_properties = "
            "additional_properties\n"
            "        return readiness_response_checks\n"
        ),
        flags=re.MULTILINE,
    )
    _rewrite_file(
        "models/sign_parts_response_urls.py",
        pattern=(
            r"        sign_parts_response_urls = cls\(\)\n"
            r"\s*sign_parts_response_urls\.additional_properties = d\n"
            r"\s*return sign_parts_response_urls\n"
        ),
        replacement=(
            "        sign_parts_response_urls = cls()\n"
            "        additional_properties: dict[str, str] = {}\n"
            "        for key, value in d.items():\n"
            "            if not isinstance(value, str):\n"
            "                raise TypeError(\n"
            '                    f"Invalid value for {key!r}: "\n'
            '                    "expected str, "\n'
            '                    f"got {type(value).__name__}"\n'
            "                )\n"
            "            additional_properties[key] = value\n\n"
            "        sign_parts_response_urls.additional_properties = "
            "additional_properties\n"
            "        return sign_parts_response_urls\n"
        ),
        flags=re.MULTILINE,
    )
    _rewrite_file(
        "models/presign_download_response.py",
        pattern=r"from attrs import define as _attrs_define\n",
        replacement=(
            "from attrs import define as _attrs_define\n"
            "from attrs import field as _attrs_field\n"
        ),
        count=1,
    )
    _rewrite_file(
        "models/presign_download_response.py",
        pattern=r"    url: str\n",
        replacement="    url: str = _attrs_field(repr=False)\n",
        count=1,
    )
    _rewrite_file(
        "models/resource_plan_request.py",
        pattern=(
            r"from typing \(\n"
            r"    Any,\n"
            r"    TypeVar,\n"
            r"    cast,\n"
            r"\)\n"
        ),
        replacement="from typing import Any, TypeVar, cast\n",
    )
    _rewrite_file(
        "models/presign_download_request.py",
        pattern=(
            r"from typing \(\n"
            r"    Any,\n"
            r"    TypeVar,\n"
            r"    cast,\n"
            r"\)\n"
        ),
        replacement="from typing import Any, TypeVar, cast\n",
    )
    _rewrite_file(
        "models/job_list_response.py",
        pattern=(
            r"from typing \(\n"
            r"    TYPE_CHECKING,\n"
            r"    Any,\n"
            r"    TypeVar,\n"
            r"\)\n"
        ),
        replacement="from typing import TYPE_CHECKING, Any, TypeVar\n",
    )

    authoritative_paths = [
        "models/job_record.py",
        "models/job_record_payload.py",
        "models/job_event_data.py",
        "models/enqueue_job_request_payload.py",
        "models/error_body_details.py",
        "models/capability_descriptor_details.py",
        "models/job_record_result_details.py",
        "models/metrics_summary_response_activity.py",
        "models/metrics_summary_response_counters.py",
        "models/metrics_summary_response_latencies_ms.py",
        "models/readiness_response_checks.py",
        "models/sign_parts_response_urls.py",
        "models/presign_download_response.py",
    ]
    checked_in_root = (
        REPO_ROOT / "packages" / "nova_sdk_py_file" / "src" / "nova_sdk_py_file"
    )
    for relative_path in authoritative_paths:
        source = checked_in_root / relative_path
        target = root / relative_path
        if not source.exists() or not target.exists():
            continue
        source_bytes = source.read_bytes()
        if target.read_bytes() != source_bytes:
            target.write_bytes(source_bytes)


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
    _repair_export_resource_output_parser(destination)
    _repair_generated_python_package(destination, target.package_name)
    _run_generated_ruff(destination)
    _repair_job_record_result_parser(destination)
    _repair_generated_python_package(destination, target.package_name)
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
