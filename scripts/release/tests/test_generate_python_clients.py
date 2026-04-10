"""Tests for public Python SDK generation helpers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.release.python_sdk import (
    GENERATOR_CONFIG_PATH,
    GENERATOR_TEMPLATE_PATH,
    PYTHON_TARGETS,
    RETAINED_TEMPLATE_FILES,
    _apply_python_model_reference_docs,
    _apply_python_sdk_repairs,
    _assert_no_generated_todo_markers,
    _generate_target_tree,
    _repair_export_resource_output_parser,
    _run_command,
)
from scripts.release.sdk_common import PUBLIC_OPENAPI_SPEC_PATH


def test_python_targets_consume_committed_public_spec() -> None:
    """Python SDK generation should share the reduced public artifact."""
    assert {target.spec_path for target in PYTHON_TARGETS} == {
        PUBLIC_OPENAPI_SPEC_PATH
    }


def test_generate_target_invokes_generator_with_config_and_templates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Generation must use the committed config and template assets."""
    commands: list[tuple[list[str], int, str]] = []

    def fake_load_spec_json(path: Path) -> dict[str, object]:
        assert path.name == "nova-file-api.public.openapi.json"
        return {"openapi": "3.1.0", "paths": {}}

    def fake_run_command(
        *,
        command: list[str],
        timeout: int,
        description: str,
    ) -> None:
        commands.append((command, timeout, description))

    formatted_roots: list[Path] = []

    monkeypatch.setattr(
        "scripts.release.python_sdk._load_spec_json",
        fake_load_spec_json,
    )
    monkeypatch.setattr(
        "scripts.release.python_sdk._run_command",
        fake_run_command,
    )
    monkeypatch.setattr(
        "scripts.release.python_sdk._run_generated_ruff",
        formatted_roots.append,
    )
    repair_spy = MagicMock()

    monkeypatch.setattr(
        "scripts.release.python_sdk._apply_python_sdk_repairs",
        repair_spy,
    )

    generation_target = PYTHON_TARGETS[0]
    target = _generate_target_tree(
        target=generation_target,
        temp_root=tmp_path,
    )

    assert target == tmp_path / "nova_sdk_py"
    assert formatted_roots == [target]
    repair_spy.assert_called_once_with(
        target,
        generation_target.package_name,
        spec={"openapi": "3.1.0", "paths": {}},
    )
    assert len(commands) == 1
    command, _timeout, description = commands[0]
    assert description == (
        f"openapi-python-client generation for {generation_target.spec_path}"
    )
    assert command[:4] == [
        sys.executable,
        "-m",
        "openapi_python_client",
        "generate",
    ]
    assert "--path" in command
    assert command[command.index("--path") + 1].endswith(
        "nova-file-api.public.openapi.json"
    )
    assert "--config" in command
    assert command[command.index("--config") + 1] == str(GENERATOR_CONFIG_PATH)
    assert "--custom-template-path" in command
    assert command[command.index("--custom-template-path") + 1] == str(
        GENERATOR_TEMPLATE_PATH
    )
    assert "--fail-on-warning" in command


def test_run_command_wraps_timeout_as_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeouts must surface as RuntimeError with command context."""

    def fake_run(
        command: list[str],
        *,
        check: bool,
        text: bool,
        capture_output: bool,
        timeout: int,
        cwd: Path,
    ) -> None:
        raise subprocess.TimeoutExpired(
            cmd=command,
            timeout=timeout,
            output=b"stdout bytes",
            stderr=b"stderr bytes",
        )

    monkeypatch.setattr("scripts.release.python_sdk.subprocess.run", fake_run)

    with pytest.raises(
        RuntimeError,
        match="example command timed out after 42s",
    ):
        _run_command(
            command=["python", "-m", "ruff"],
            timeout=42,
            description="example command",
        )


def test_python_sdk_template_override_set_stays_minimal() -> None:
    """Only the retained contract-shaping Python templates should remain."""
    actual_files = tuple(
        path.relative_to(GENERATOR_TEMPLATE_PATH).as_posix()
        for path in sorted(GENERATOR_TEMPLATE_PATH.rglob("*.jinja"))
        if path.is_file()
    )

    assert actual_files == RETAINED_TEMPLATE_FILES


def test_repair_export_resource_output_parser_adds_mapping_cast(
    tmp_path: Path,
) -> None:
    """The nullable export-output parser fix should stay narrow."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    export_resource = models_dir / "export_resource.py"
    export_resource.write_text(
        "        def _parse_output(data: object):\n"
        "                if not isinstance(data, dict):\n"
        "                    raise TypeError()\n"
        "                output_type_0 = ExportOutput.from_dict(data)\n"
        '        output = _parse_output(d.pop("output", UNSET))\n',
        encoding="utf-8",
    )

    _repair_export_resource_output_parser(tmp_path)
    first_pass = export_resource.read_text(encoding="utf-8")
    _repair_export_resource_output_parser(tmp_path)
    second_pass = export_resource.read_text(encoding="utf-8")

    assert "if not isinstance(data, Mapping):" in first_pass
    assert 'output_data = cast("Mapping[str, Any]", data)' in first_pass
    assert "return ExportOutput.from_dict(output_data)" in first_pass
    assert first_pass == second_pass


def test_apply_python_sdk_repairs_preserves_typed_maps_and_redacted_repr(
    tmp_path: Path,
) -> None:
    """Residual package repairs should stay limited to current schema quirks."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "metrics_summary_response_activity.py").write_text(
        "class MetricsSummaryResponseActivity:\n"
        '    """ """\n\n'
        "        metrics_summary_response_activity = cls()\n"
        "        metrics_summary_response_activity.additional_properties = d\n"
        "        return metrics_summary_response_activity\n",
        encoding="utf-8",
    )
    (models_dir / "sign_parts_response_urls.py").write_text(
        "class SignPartsResponseUrls:\n"
        '    """ """\n\n'
        "        sign_parts_response_urls = cls()\n"
        "        sign_parts_response_urls.additional_properties = d\n"
        "        return sign_parts_response_urls\n",
        encoding="utf-8",
    )
    (models_dir / "presign_download_response.py").write_text(
        "from attrs import define as _attrs_define\n\n"
        "@_attrs_define\n"
        "class PresignDownloadResponse:\n"
        "    url: str\n",
        encoding="utf-8",
    )
    (models_dir / "initiate_upload_response.py").write_text(
        "from attrs import define as _attrs_define\n"
        "from ..types import UNSET, Unset\n\n"
        "@_attrs_define\n"
        "class InitiateUploadResponse:\n"
        "    url: None | str | Unset = UNSET\n",
        encoding="utf-8",
    )
    (models_dir / "complete_upload_request.py").write_text(
        "from __future__ import annotations\n\n"
        "from typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n"
        "    from ..models.completed_part import CompletedPart\n",
        encoding="utf-8",
    )
    (tmp_path / "__init__.py").write_text(
        '"""A client library for accessing nova-file-api"""\n'
        "from .client import AuthenticatedClient, Client\n\n"
        "__all__ = (\n"
        '    "AuthenticatedClient",\n'
        '    "Client",\n'
        ")\n",
        encoding="utf-8",
    )

    _apply_python_sdk_repairs(tmp_path, "nova_sdk_py")
    first_pass = {
        path.name: path.read_text(encoding="utf-8")
        for path in (
            models_dir / "metrics_summary_response_activity.py",
            models_dir / "sign_parts_response_urls.py",
            models_dir / "presign_download_response.py",
            models_dir / "initiate_upload_response.py",
            models_dir / "complete_upload_request.py",
            tmp_path / "__init__.py",
        )
    }
    _apply_python_sdk_repairs(tmp_path, "nova_sdk_py")
    second_pass = {
        path.name: path.read_text(encoding="utf-8")
        for path in (
            models_dir / "metrics_summary_response_activity.py",
            models_dir / "sign_parts_response_urls.py",
            models_dir / "presign_download_response.py",
            models_dir / "initiate_upload_response.py",
            models_dir / "complete_upload_request.py",
            tmp_path / "__init__.py",
        )
    }

    activity = first_pass["metrics_summary_response_activity.py"]
    sign_parts = first_pass["sign_parts_response_urls.py"]
    presign = first_pass["presign_download_response.py"]
    initiate_upload = first_pass["initiate_upload_response.py"]
    complete_upload = first_pass["complete_upload_request.py"]
    package_init = first_pass["__init__.py"]

    assert "additional_properties: dict[str, int] = {}" in activity
    assert "additional_properties: dict[str, str] = {}" in sign_parts
    assert "if not isinstance(value, str):" in sign_parts
    assert "raise TypeError(" in sign_parts
    assert "from attrs import field as _attrs_field" in presign
    assert "url: str = _attrs_field(repr=False)" in presign
    assert "from nova_sdk_py.types import UNSET, Unset" in initiate_upload
    assert "from attrs import field as _attrs_field" in initiate_upload
    assert "url: None | str | Unset = _attrs_field(" in initiate_upload
    assert "default=UNSET, repr=False" in initiate_upload
    assert (
        "from nova_sdk_py.models.completed_part import CompletedPart"
        in complete_upload
    )
    assert package_init == (
        '"""A client library for accessing nova-file-api"""\n'
        "from .client import AuthenticatedClient, Client\n\n"
        "__all__ = (\n"
        '    "AuthenticatedClient",\n'
        '    "Client",\n'
        ")\n"
    )
    assert first_pass == second_pass


def test_assert_no_generated_todo_markers_fails_on_remaining_markers(
    tmp_path: Path,
) -> None:
    """Generated Python SDK trees must fail loudly on lingering TODO markers."""
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "example.py").write_text(
        "# TODO: remove this repair\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="unresolved TODO markers"):
        _assert_no_generated_todo_markers(tmp_path)


def test_apply_python_sdk_repairs_preserves_canonical_readiness_exports(
    tmp_path: Path,
) -> None:
    """The generated package should keep only canonical readiness exports."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    package_init = models_dir / "__init__.py"
    package_init.write_text(
        '"""Contains all the data models used in inputs/outputs"""\n\n'
        "from .readiness_checks import ReadinessChecks\n"
        "from .readiness_response import ReadinessResponse\n\n"
        "from .validation_error_context import ValidationErrorContext\n\n"
        "__all__ = (\n"
        '    "ReadinessChecks",\n'
        '    "ReadinessResponse",\n'
        '    "ValidationErrorContext",\n'
        ")\n",
        encoding="utf-8",
    )

    _apply_python_sdk_repairs(tmp_path, "nova_sdk_py")
    first_pass = package_init.read_text(encoding="utf-8")
    _apply_python_sdk_repairs(tmp_path, "nova_sdk_py")
    second_pass = package_init.read_text(encoding="utf-8")

    assert "ReadinessResponseChecks" not in first_pass
    assert first_pass == second_pass


def test_apply_python_sdk_repairs_normalizes_single_line_docstrings(
    tmp_path: Path,
) -> None:
    """Generated single-line docstrings should be trimmed and wrapped."""
    client_path = tmp_path / "client.py"
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    model_path = models_dir / "example.py"

    client_path.write_text(
        "class Client:\n"
        "    field: str\n"
        '    """ This docstring should be trimmed and wrapped because it is '
        "long enough to exceed the local line length policy for generated "
        'single-line docstrings. """\n',
        encoding="utf-8",
    )
    model_path.write_text(
        'class Example:\n    value: str\n    """ Example value. """\n',
        encoding="utf-8",
    )

    _apply_python_sdk_repairs(tmp_path, "nova_sdk_py")

    client_source = client_path.read_text(encoding="utf-8")
    model_source = model_path.read_text(encoding="utf-8")

    assert '""" Example value. """' not in model_source
    assert '"""Example value."""' in model_source
    assert (
        '""" This docstring should be trimmed and wrapped because it is long'
        not in client_source
    )
    assert "single-line docstrings." in client_source


def test_apply_python_sdk_repairs_injects_structured_operation_docstrings(
    tmp_path: Path,
) -> None:
    """Spec-driven public Python docs should include structured sections."""
    module_path = tmp_path / "api" / "transfers" / "initiate_upload.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text(
        "from ...client import AuthenticatedClient\n"
        "from ...models.error_envelope import ErrorEnvelope\n"
        "from ...models.initiate_upload_request import InitiateUploadRequest\n"
        "from ...models.initiate_upload_response import "
        "InitiateUploadResponse\n"
        "from ...types import Response, UNSET, Unset\n\n"
        "def sync_detailed(\n"
        "    *,\n"
        "    client: AuthenticatedClient,\n"
        "    body: InitiateUploadRequest,\n"
        "    idempotency_key: None | str | Unset = UNSET,\n"
        ") -> Response[ErrorEnvelope | InitiateUploadResponse]:\n"
        '    """Old docstring."""\n'
        "    raise NotImplementedError\n",
        encoding="utf-8",
    )
    spec = {
        "paths": {
            "/v1/transfers/uploads/initiate": {
                "post": {
                    "operationId": "initiate_upload",
                    "tags": ["transfers"],
                    "summary": "Initiate a direct-to-S3 upload session",
                    "description": (
                        "Resolve the effective transfer policy for the caller "
                        "and return the presigned metadata needed to upload "
                        "directly to S3."
                    ),
                    "parameters": [
                        {
                            "in": "header",
                            "name": "Idempotency-Key",
                            "description": (
                                "Client-supplied idempotency key used to "
                                "deduplicate supported mutation requests."
                            ),
                        }
                    ],
                    "requestBody": {
                        "description": "Transfer-initiation request payload.",
                    },
                }
            }
        }
    }

    _apply_python_sdk_repairs(tmp_path, "nova_sdk_py", spec=spec)

    source = module_path.read_text(encoding="utf-8")

    assert "Args:" in source
    assert "client (AuthenticatedClient):" in source
    assert "body (InitiateUploadRequest): Transfer-initiation request" in source
    assert "Returns:" in source
    assert "Response[ErrorEnvelope | InitiateUploadResponse]:" in source
    assert "response wrapper containing the parsed response payload." in source
    assert "Raises:" in source


def test_apply_python_model_reference_docs_keeps_backslashes_literal(
    tmp_path: Path,
) -> None:
    """Model docstring rewrites should not treat backslashes as escapes."""
    model_path = tmp_path / "models" / "example.py"
    model_path.parent.mkdir(parents=True)
    model_path.write_text(
        "from attrs import define as _attrs_define\n\n"
        "@_attrs_define\n"
        "class Example:\n"
        "    value: str\n",
        encoding="utf-8",
    )

    _apply_python_model_reference_docs(
        tmp_path,
        spec={
            "components": {
                "schemas": {
                    "Example": {
                        "description": r"Matches the literal path C:\\temp.",
                        "properties": {
                            "value": {
                                "description": r"Literal segment C:\\temp."
                            }
                        },
                    }
                }
            }
        },
    )

    source = model_path.read_text(encoding="utf-8")
    assert r"Matches the literal path C:\\temp." in source
    assert r"value: Literal segment C:\\temp." in source
