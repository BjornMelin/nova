"""Tests for Auth0 overlay contract validation."""

from __future__ import annotations

from pathlib import Path

from scripts.release import validate_auth0_contract


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_repo_fixture(tmp_path: Path) -> Path:
    repo_root = tmp_path
    _write(
        repo_root / "infra/auth0/tenant/tenant.yaml",
        "\n".join(
            [
                "client:",
                "  callback: '@@WEB_CALLBACK_URL@@'",
                "  origin: '@@WEB_ORIGIN@@'",
                "",
            ]
        ),
    )
    _write(
        repo_root / "infra/auth0/mappings/dev.json",
        "\n".join(
            [
                '{"WEB_CALLBACK_URL": "https://dev.example.com/callback",',
                ' "WEB_ORIGIN": "https://dev.example.com"}',
                "",
            ]
        ),
    )
    _write(
        repo_root / "infra/auth0/env/dev.env.example",
        "\n".join(
            [
                "AUTH0_ALLOW_DELETE=false",
                "AUTH0_INPUT_FILE=infra/auth0/tenant/tenant.yaml",
                "AUTH0_KEYWORD_MAPPINGS_FILE=infra/auth0/mappings/dev.json",
                "",
            ]
        ),
    )
    return repo_root


def test_run_validation_passes_for_valid_overlay(tmp_path: Path) -> None:
    repo_root = _create_repo_fixture(tmp_path)

    errors = validate_auth0_contract.run_validation(repo_root)

    assert errors == []


def test_run_validation_fails_for_missing_mapping_token(tmp_path: Path) -> None:
    repo_root = _create_repo_fixture(tmp_path)
    _write(
        repo_root / "infra/auth0/mappings/dev.json",
        '{"WEB_CALLBACK_URL": "https://dev.example.com/callback"}\n',
    )

    errors = validate_auth0_contract.run_validation(repo_root)

    assert len(errors) == 1
    assert "missing token keys: WEB_ORIGIN" in errors[0]


def test_run_validation_fails_for_delete_guard_override(tmp_path: Path) -> None:
    repo_root = _create_repo_fixture(tmp_path)
    _write(
        repo_root / "infra/auth0/env/dev.env.example",
        "\n".join(
            [
                "AUTH0_ALLOW_DELETE=true",
                "AUTH0_INPUT_FILE=infra/auth0/tenant/tenant.yaml",
                "AUTH0_KEYWORD_MAPPINGS_FILE=infra/auth0/mappings/dev.json",
                "",
            ]
        ),
    )

    errors = validate_auth0_contract.run_validation(repo_root)

    assert len(errors) == 1
    assert "AUTH0_ALLOW_DELETE must be 'false'" in errors[0]
