"""Tests for public Python SDK generation helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts.release.generate_python_clients import (
    GENERATOR_CONFIG_PATH,
    GENERATOR_TEMPLATE_PATH,
    TARGETS,
    _filter_internal_operations_for_public_sdk,
    _generate_target,
    _repair_job_record_result_parser,
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
        "scripts.release.generate_python_clients._load_spec_json",
        fake_load_spec_json,
    )
    monkeypatch.setattr(
        "scripts.release.generate_python_clients._write_temp_spec",
        fake_write_temp_spec,
    )
    monkeypatch.setattr(
        "scripts.release.generate_python_clients._run_command",
        fake_run_command,
    )
    monkeypatch.setattr(
        "scripts.release.generate_python_clients._run_generated_ruff",
        formatted_roots.append,
    )

    generation_target = TARGETS[0]
    target = _generate_target(target=generation_target, temp_root=tmp_path)

    assert target == tmp_path / "nova_sdk_py_file"
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


def test_repair_job_record_result_parser_adds_mapping_cast(
    tmp_path: Path,
) -> None:
    """The residual ty fix should stay narrow and idempotent."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    job_record = models_dir / "job_record.py"
    job_record.write_text(
        "        def _parse_result(data: object):\n"
        "                if not isinstance(data, dict):\n"
        "                    raise TypeError()\n"
        "                result_type_0 = "
        "JobRecordResultDetails.from_dict(data)\n"
        '        result = _parse_result(d.pop("result", UNSET))\n',
        encoding="utf-8",
    )

    _repair_job_record_result_parser(tmp_path)
    first_pass = job_record.read_text(encoding="utf-8")
    _repair_job_record_result_parser(tmp_path)
    second_pass = job_record.read_text(encoding="utf-8")

    assert "if not isinstance(data, Mapping):" in first_pass
    assert 'result_data = cast("Mapping[str, Any]", data)' in first_pass
    assert first_pass == second_pass
