"""Python SDK generation helpers."""

from __future__ import annotations

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
from typing import Any, Literal, cast

from nova_runtime_support import (
    SDK_VISIBILITY_EXTENSION,
    SDK_VISIBILITY_INTERNAL,
)
from scripts.release.sdk_common import REPO_ROOT

OPENAPI_ROOT = REPO_ROOT / "packages" / "contracts" / "openapi"
GENERATOR_ROOT = REPO_ROOT / "scripts" / "release" / "openapi_python_client"
GENERATOR_CONFIG_PATH = GENERATOR_ROOT / "config.yaml"
GENERATOR_TEMPLATE_PATH = GENERATOR_ROOT / "templates"
RETAINED_TEMPLATE_FILES = (
    "client.py.jinja",
    "endpoint_module.py.jinja",
    "errors.py.jinja",
    "types.py.jinja",
)
_IGNORED_PARTS = {"__pycache__"}
_IGNORED_PREFIXES = (".",)
_GENERATOR_TIMEOUT_SECONDS = 60
_FORMATTER_TIMEOUT_SECONDS = 60
_HTTP_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
)


@dataclass(frozen=True)
class PythonGenerationTarget:
    """Python SDK package synced from one committed OpenAPI document."""

    spec_path: Path
    output_path: Path
    package_name: str


@dataclass(frozen=True)
class AdditionalPropertiesRepair:
    """One retained typed-map repair for generated model output."""

    relative_path: str
    value_kind: Literal["int", "float", "bool", "str"]


PYTHON_TARGETS = (
    PythonGenerationTarget(
        spec_path=OPENAPI_ROOT / "nova-file-api.openapi.json",
        output_path=(
            REPO_ROOT / "packages" / "nova_sdk_py" / "src" / "nova_sdk_py"
        ),
        package_name="nova_sdk_py",
    ),
)

_ADDITIONAL_PROPERTIES_REPAIRS = (
    AdditionalPropertiesRepair(
        relative_path="models/metrics_summary_response_activity.py",
        value_kind="int",
    ),
    AdditionalPropertiesRepair(
        relative_path="models/metrics_summary_response_counters.py",
        value_kind="int",
    ),
    AdditionalPropertiesRepair(
        relative_path="models/metrics_summary_response_latencies_ms.py",
        value_kind="float",
    ),
    AdditionalPropertiesRepair(
        relative_path="models/readiness_response_checks.py",
        value_kind="bool",
    ),
    AdditionalPropertiesRepair(
        relative_path="models/sign_parts_response_urls.py",
        value_kind="str",
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


def _rewrite_file(
    root: Path,
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
    if replacement in content:
        return
    updated, replaced = re.subn(
        pattern,
        replacement,
        content,
        count=count,
        flags=flags,
    )
    if replaced == 0:
        raise RuntimeError(
            f"expected rewrite pattern not found in {path.relative_to(root)}"
        )
    if updated != content:
        path.write_text(updated, encoding="utf-8")


def _render_additional_properties_replacement(
    *,
    instance_name: str,
    repair: AdditionalPropertiesRepair,
) -> str:
    if repair.value_kind == "str":
        return (
            f"        {instance_name} = cls()\n"
            "        additional_properties: dict[str, str] = {}\n"
            "        for key, value in d.items():\n"
            "            if not isinstance(value, str):\n"
            "                raise TypeError(\n"
            '                    f"Invalid value for {key!r}: expected str, "\n'
            '                    f"got {type(value).__name__}"\n'
            "                )\n"
            "            additional_properties[str(key)] = value\n\n"
            f"        {instance_name}.additional_properties = "
            "additional_properties\n"
            f"        return {instance_name}\n"
        )

    converter = "int" if repair.value_kind == "int" else repair.value_kind
    lines = [
        f"        {instance_name} = cls()",
        f"        additional_properties: dict[str, {repair.value_kind}] = {{}}",
        "        for key, value in d.items():",
    ]
    if repair.value_kind in {"int", "float"}:
        lines.extend(
            [
                "            if isinstance(value, bool):",
                "                raise TypeError(",
                '                    f"Invalid value for {key!r}: '
                f'expected {repair.value_kind}, got bool"',
                "                )",
            ]
        )
    elif repair.value_kind == "bool":
        lines.extend(
            [
                "            if not isinstance(value, bool):",
                "                raise TypeError(",
                '                    f"Invalid value for {key!r}: "',
                '                    "expected bool, "',
                '                    f"got {type(value).__name__}"',
                "                )",
            ]
        )
    lines.append(f"            additional_properties[key] = {converter}(value)")
    lines.extend(
        [
            "",
            f"        {instance_name}.additional_properties = "
            "additional_properties",
            f"        return {instance_name}",
            "",
        ]
    )
    return "\n".join(lines)


def _apply_typed_additional_properties_repairs(root: Path) -> None:
    for repair in _ADDITIONAL_PROPERTIES_REPAIRS:
        instance_name = Path(repair.relative_path).stem
        _rewrite_file(
            root,
            repair.relative_path,
            pattern=(
                rf"        {instance_name} = cls\(\s*\)\n"
                rf"\s*{instance_name}\.additional_properties = d\n"
                rf"\s*return {instance_name}\n"
            ),
            replacement=_render_additional_properties_replacement(
                instance_name=instance_name,
                repair=repair,
            ),
            flags=re.MULTILINE,
        )


def _redact_presign_download_url_repr(root: Path) -> None:
    _rewrite_file(
        root,
        "models/presign_download_response.py",
        pattern=r"from attrs import define as _attrs_define\n",
        replacement=(
            "from attrs import define as _attrs_define\n"
            "from attrs import field as _attrs_field\n"
        ),
        count=1,
    )
    _rewrite_file(
        root,
        "models/presign_download_response.py",
        pattern=r"    url: str\n",
        replacement="    url: str = _attrs_field(repr=False)\n",
        count=1,
    )
    _rewrite_file(
        root,
        "models/initiate_upload_response.py",
        pattern=r"from attrs import define as _attrs_define\n",
        replacement=(
            "from attrs import define as _attrs_define\n"
            "from attrs import field as _attrs_field\n"
        ),
        count=1,
    )
    _rewrite_file(
        root,
        "models/initiate_upload_response.py",
        pattern=r"    url: None \| str \| Unset = UNSET\n",
        replacement=(
            "    url: None | str | Unset = _attrs_field(\n"
            "        default=UNSET, repr=False\n"
            "    )\n"
        ),
        count=1,
    )


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


def _repair_sign_parts_request_checksum_parser(root: Path) -> None:
    path = root / "models" / "sign_parts_request.py"
    if not path.exists():
        return

    content = path.read_text(encoding="utf-8")
    checksum_repaired = (
        "SignPartsRequestChecksumsSha256Type0.from_dict(\n"
        '                        cast("Mapping[str, Any]", data)\n'
        "                    )"
    )
    if checksum_repaired in content:
        return

    markers = (
        "SignPartsRequestChecksumsSha256Type0.from_dict(data)",
        (
            "SignPartsRequestChecksumsSha256Type0.from_dict(\n"
            "                    data\n"
            "                )"
        ),
        (
            "SignPartsRequestChecksumsSha256Type0.from_dict(\n"
            "                        data\n"
            "                    )"
        ),
    )
    for marker in markers:
        if marker in content:
            updated = content.replace(
                marker,
                (
                    "SignPartsRequestChecksumsSha256Type0.from_dict(\n"
                    '                        cast("Mapping[str, Any]", data)\n'
                    "                    )"
                ),
                1,
            )
            path.write_text(updated, encoding="utf-8")
            return

    raise RuntimeError(
        "expected SignPartsRequest checksum parser snippet not found in "
        f"{path.relative_to(root)}"
    )


def _ensure_validation_error_context_file(root: Path) -> None:
    """Rewrite ``validation_error_context.py`` when codegen output is wrong.

    The attrs model is emitted without a module docstring; this helper writes
    the full file when the expected marker is missing (not a docstring-only
    edit).
    """
    path = root / "models" / "validation_error_context.py"
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8")
    if (
        "Hold arbitrary key/value pairs returned alongside validation errors"
        in content
    ):
        return
    if "class ValidationErrorContext" not in content:
        return
    path.write_text(
        '''\
"""Context for HTTP validation error payloads (additionalProperties)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define, field as _attrs_field

T = TypeVar("T", bound="ValidationErrorContext")


@_attrs_define
class ValidationErrorContext:
    """Hold arbitrary key/value pairs returned alongside validation errors.

    Attributes:
        additional_properties: Extra response members preserved from the
            decoded payload.
    """

    additional_properties: dict[str, Any] = _attrs_field(
        init=False, factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize additional properties to a plain ``dict``.

        Returns:
            Mapping of preserved validation-error context values.
        """

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        """Build an instance from a decoded mapping.

        Args:
            src_dict: Decoded mapping containing arbitrary context members.

        Returns:
            New ``ValidationErrorContext`` containing all supplied keys.
        """

        d = dict(src_dict)
        validation_error_context = cls()

        validation_error_context.additional_properties = d
        return validation_error_context

    @property
    def additional_keys(self) -> list[str]:
        """Return keys present in ``additional_properties``.

        Returns:
            Ordered list of preserved context keys.
        """

        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        """Return the value for ``key`` from ``additional_properties``.

        Args:
            key: Context key to retrieve.

        Returns:
            Stored value for ``key``.

        Raises:
            KeyError: If ``key`` is not present.
        """

        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set ``key`` on ``additional_properties``.

        Args:
            key: Context key to update.
            value: Value to store for ``key``.

        Returns:
            None.
        """

        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        """Remove ``key`` from ``additional_properties``.

        Args:
            key: Context key to remove.

        Returns:
            None.

        Raises:
            KeyError: If ``key`` is not present.
        """

        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        """Return whether ``key`` exists in ``additional_properties``.

        Args:
            key: Context key to test.

        Returns:
            ``True`` when ``key`` is present, else ``False``.
        """

        return key in self.additional_properties
''',
        encoding="utf-8",
    )


def _apply_python_sdk_repairs(root: Path, package_name: str) -> None:
    _apply_typed_additional_properties_repairs(root)
    _redact_presign_download_url_repr(root)
    _repair_export_resource_output_parser(root)
    _repair_sign_parts_request_checksum_parser(root)
    _ensure_validation_error_context_file(root)
    _repair_relative_imports_to_absolute(root, package_name)
    _repair_blank_model_docstrings(root)
    _repair_model_docstring_indentation(root)


def _repair_model_docstring_indentation(root: Path) -> None:
    model_dir = root / "models"
    if not model_dir.exists():
        return
    for path in sorted(model_dir.glob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        updated_lines: list[str] = []
        in_attributes_block = False
        for line in lines:
            if line == "        Attributes:":
                updated_lines.append("    Attributes:")
                in_attributes_block = True
                continue
            if in_attributes_block:
                if line.startswith("            ") and line.strip():
                    updated_lines.append(line[4:])
                    continue
                if line.strip() in {'"""', "'''"} or not line.strip():
                    in_attributes_block = False
            updated_lines.append(line)
        updated = "\n".join(updated_lines) + "\n"
        original = "\n".join(lines) + "\n"
        if updated != original:
            path.write_text(updated, encoding="utf-8")


def _repair_relative_imports_to_absolute(root: Path, package_name: str) -> None:
    model_dir = root / "models"
    if not model_dir.exists():
        return

    for path in sorted(model_dir.glob("*.py")):
        content = path.read_text(encoding="utf-8")
        updated = re.sub(
            r"(?m)^(?P<indent>\s*)from\s+\.\.(?P<module>[A-Za-z_][\w.]*)\s+import\s+",
            rf"\g<indent>from {package_name}.\g<module> import ",
            content,
        )
        if updated != content:
            path.write_text(updated, encoding="utf-8")


def _render_model_docstring(class_name: str) -> str:
    return f'    """Model representing {class_name}."""\n'


def _render_blank_model_docstring_replacement(
    match: re.Match[str],
    *,
    class_name: str,
) -> str:
    return f'{match.group("indent")}"""Model representing {class_name}."""\n'


def _repair_blank_model_docstrings(root: Path) -> None:
    model_dir = root / "models"
    if not model_dir.exists():
        return

    for path in sorted(model_dir.glob("*.py")):
        content = path.read_text(encoding="utf-8")
        class_name = "".join(part.capitalize() for part in path.stem.split("_"))
        replacement = partial(
            _render_blank_model_docstring_replacement,
            class_name=class_name,
        )

        for pattern in (
            re.compile(r'(?m)^(?P<indent>\s*)"""\s+"""\s*$'),
            re.compile(r'(?m)^(?P<indent>\s*)"""\s*\n\s*"""\s*$'),
        ):
            updated, replaced = pattern.subn(
                replacement,
                content,
                count=1,
            )
            if replaced:
                path.write_text(updated, encoding="utf-8")
                break


def _run_command(*, command: list[str], timeout: int, description: str) -> None:
    try:
        result = subprocess.run(  # noqa: S603
            command,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd=REPO_ROOT,
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
            f"{description} timed out after {timeout}s:\n"
            f"command:\n{command}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        ) from exc
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
    if not GENERATOR_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"required generator asset missing: {GENERATOR_CONFIG_PATH}"
        )
    if not GENERATOR_TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"required generator asset missing: {GENERATOR_TEMPLATE_PATH}"
        )
    actual_templates = tuple(
        path.relative_to(GENERATOR_TEMPLATE_PATH).as_posix()
        for path in sorted(GENERATOR_TEMPLATE_PATH.rglob("*.jinja"))
        if path.is_file()
    )
    if actual_templates != RETAINED_TEMPLATE_FILES:
        raise RuntimeError(
            f"unexpected Python SDK template override set: {actual_templates!r}"
        )


def _generate_target_tree(
    target: PythonGenerationTarget,
    temp_root: Path,
) -> Path:
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
    _run_command(
        command=command,
        timeout=_GENERATOR_TIMEOUT_SECONDS,
        description=f"openapi-python-client generation for {target.spec_path}",
    )

    _apply_python_sdk_repairs(destination, target.package_name)
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


def generate_or_check_python_sdk(
    target: PythonGenerationTarget,
    *,
    check: bool,
) -> list[str]:
    """Generate or verify the committed Python SDK tree for one target.

    Args:
        target: The Python generation target that defines the committed
            OpenAPI source, output package root, and package name.
        check: When `True`, compare the generated tree against the committed
            package tree and report drift instead of syncing files in place.

    Returns:
        A list of stale-artifact issues. The list is empty when the committed
        tree already matches the generated output.

    Raises:
        FileNotFoundError: If the OpenAPI source or generator assets are
            missing.
        RuntimeError: If generation, repair application, or Ruff validation
            fails.
        TypeError: If the OpenAPI document has an unexpected shape.
    """
    issues: list[str] = []
    with TemporaryDirectory() as temp_dir:
        generated_root = _generate_target_tree(
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


def generate_or_check_python_sdks(*, check: bool) -> list[str]:
    """Generate or verify all committed Python SDK artifacts.

    Args:
        check: When `True`, validate that all committed Python SDK trees match
            freshly generated output instead of rewriting files in place.

    Returns:
        A flattened list of stale-artifact issues across all configured
        Python generation targets.

    Raises:
        FileNotFoundError: If any configured OpenAPI source or generator asset
            is missing.
        RuntimeError: If any generation, repair, or validation step fails for
            a configured target.
        TypeError: If any configured OpenAPI document has an unexpected shape.
    """
    issues: list[str] = []
    for target in PYTHON_TARGETS:
        issues.extend(generate_or_check_python_sdk(target, check=check))
    return issues
