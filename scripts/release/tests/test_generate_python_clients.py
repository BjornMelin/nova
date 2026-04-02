"""Tests for public Python SDK generation helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts.release.python_sdk import (
    GENERATOR_CONFIG_PATH,
    GENERATOR_TEMPLATE_PATH,
    PYTHON_TARGETS,
    RETAINED_TEMPLATE_FILES,
    _apply_python_sdk_repairs,
    _filter_internal_operations_for_public_sdk,
    _generate_target_tree,
    _repair_export_resource_output_parser,
)


def test_filter_internal_operations_prunes_internal_only_paths() -> None:
    """Internal-only operations should be removed before generation."""
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/v1/public": {
                "get": {
                    "operationId": "get_public",
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/v1/internal": {
                "post": {
                    "operationId": "post_internal",
                    "x-nova-sdk-visibility": "internal",
                    "responses": {"202": {"description": "accepted"}},
                }
            },
            "/v1/mixed": {
                "get": {
                    "operationId": "get_mixed",
                    "responses": {"200": {"description": "ok"}},
                },
                "post": {
                    "operationId": "post_mixed_internal",
                    "x-nova-sdk-visibility": "internal",
                    "responses": {"202": {"description": "accepted"}},
                },
            },
        },
    }

    filtered = _filter_internal_operations_for_public_sdk(spec)

    assert "/v1/public" in filtered["paths"]
    assert filtered["paths"]["/v1/public"]["get"]["operationId"] == "get_public"
    assert "/v1/internal" not in filtered["paths"]
    assert "get" in filtered["paths"]["/v1/mixed"]
    assert "post" not in filtered["paths"]["/v1/mixed"]


def test_generate_target_invokes_generator_with_config_and_templates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Generation must use the committed config and template assets."""
    commands: list[tuple[list[str], int, str]] = []

    def fake_load_spec_json(path: Path) -> dict[str, object]:
        assert path.name == "nova-file-api.openapi.json"
        return {"openapi": "3.1.0", "paths": {}}

    def fake_write_temp_spec(
        *,
        spec: dict[str, object],
        destination: Path,
    ) -> Path:
        destination.write_text("{}", encoding="utf-8")
        assert spec == {"openapi": "3.1.0", "paths": {}}
        return destination

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
        "scripts.release.python_sdk._write_temp_spec",
        fake_write_temp_spec,
    )
    monkeypatch.setattr(
        "scripts.release.python_sdk._run_command",
        fake_run_command,
    )
    monkeypatch.setattr(
        "scripts.release.python_sdk._run_generated_ruff",
        formatted_roots.append,
    )
    monkeypatch.setattr(
        "scripts.release.python_sdk._apply_python_sdk_repairs",
        lambda _root: None,
    )

    generation_target = PYTHON_TARGETS[0]
    target = _generate_target_tree(
        target=generation_target,
        temp_root=tmp_path,
    )

    assert target == tmp_path / "nova_sdk_py"
    assert formatted_roots == [target]
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
    assert "--config" in command
    assert command[command.index("--config") + 1] == str(GENERATOR_CONFIG_PATH)
    assert "--custom-template-path" in command
    assert command[command.index("--custom-template-path") + 1] == str(
        GENERATOR_TEMPLATE_PATH
    )
    assert "--fail-on-warning" in command


def test_python_sdk_template_override_set_stays_minimal() -> None:
    """Only the retained contract-shaping Python templates should remain."""
    actual_files = tuple(
        path.name
        for path in sorted(GENERATOR_TEMPLATE_PATH.glob("*.jinja"))
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
    (models_dir / "readiness_response_checks.py").write_text(
        "class ReadinessResponseChecks:\n"
        '    """ """\n\n'
        "        readiness_response_checks = cls()\n"
        "        readiness_response_checks.additional_properties = d\n"
        "        return readiness_response_checks\n",
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
    (tmp_path / "__init__.py").write_text(
        '"""A client library for accessing nova-file-api"""\n'
        "from .client import AuthenticatedClient, Client\n\n"
        "__all__ = (\n"
        '    "AuthenticatedClient",\n'
        '    "Client",\n'
        ")\n",
        encoding="utf-8",
    )

    _apply_python_sdk_repairs(tmp_path)
    first_pass = {
        path.name: path.read_text(encoding="utf-8")
        for path in (
            models_dir / "metrics_summary_response_activity.py",
            models_dir / "readiness_response_checks.py",
            models_dir / "sign_parts_response_urls.py",
            models_dir / "presign_download_response.py",
            tmp_path / "__init__.py",
        )
    }
    _apply_python_sdk_repairs(tmp_path)
    second_pass = {
        path.name: path.read_text(encoding="utf-8")
        for path in (
            models_dir / "metrics_summary_response_activity.py",
            models_dir / "readiness_response_checks.py",
            models_dir / "sign_parts_response_urls.py",
            models_dir / "presign_download_response.py",
            tmp_path / "__init__.py",
        )
    }

    activity = first_pass["metrics_summary_response_activity.py"]
    readiness = first_pass["readiness_response_checks.py"]
    sign_parts = first_pass["sign_parts_response_urls.py"]
    presign = first_pass["presign_download_response.py"]
    package_init = first_pass["__init__.py"]

    assert "additional_properties: dict[str, int] = {}" in activity
    assert "additional_properties: dict[str, bool] = {}" in readiness
    assert "str(key): str(value) for key, value in d.items()" in sign_parts
    assert "from attrs import field as _attrs_field" in presign
    assert "url: str = _attrs_field(repr=False)" in presign
    assert package_init == (
        '"""A client library for accessing nova-file-api"""\n'
        "from .client import AuthenticatedClient, Client\n\n"
        "__all__ = (\n"
        '    "AuthenticatedClient",\n'
        '    "Client",\n'
        ")\n"
    )
    assert first_pass == second_pass
