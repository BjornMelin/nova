# mypy: disable-error-code=no-untyped-def

"""Tests for the safe Auth0 Deploy CLI wrapper."""

from __future__ import annotations

from pathlib import Path

from scripts.release import run_auth0_deploy_cli


def test_build_base_env_requires_expected_keys(tmp_path: Path) -> None:
    env_file = tmp_path / "dev.env"
    env_file.write_text("AUTH0_DOMAIN=example.auth0.com\n", encoding="utf-8")

    try:
        run_auth0_deploy_cli._build_base_env(env_file)
    except ValueError as exc:
        assert "env file is missing required keys" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_build_base_env_passes_included_only_and_mapping(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_file = tmp_path / "dev.env"
    mapping_dir = tmp_path / "tmp"
    mapping_dir.mkdir()
    mapping_file = mapping_dir / "dev.json"
    env_file.write_text(
        "\n".join(
            [
                "AUTH0_DOMAIN=example.auth0.com",
                "AUTH0_CLIENT_ID=client_id",
                "AUTH0_CLIENT_SECRET=client_secret",
                "AUTH0_ALLOW_DELETE=false",
                'AUTH0_INCLUDED_ONLY=["tenant","resourceServers","clients","clientGrants"]',
                "AUTH0_KEYWORD_MAPPINGS_FILE=tmp/dev.json",
                "",
            ]
        ),
        encoding="utf-8",
    )
    mapping_file.write_text('{"ENV":"dev"}\n', encoding="utf-8")
    monkeypatch.setattr(run_auth0_deploy_cli, "_repo_root", lambda: tmp_path)

    base_env = run_auth0_deploy_cli._build_base_env(env_file)

    assert (
        base_env["AUTH0_INCLUDED_ONLY"]
        == '["tenant","resourceServers","clients","clientGrants"]'
    )
    assert base_env["AUTH0_KEYWORD_REPLACE_MAPPINGS"] == '{"ENV":"dev"}\n'


def test_build_base_env_rejects_delete_enabled_overlay(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_file = tmp_path / "dev.env"
    mapping_dir = tmp_path / "tmp"
    mapping_dir.mkdir()
    (mapping_dir / "dev.json").write_text('{"ENV":"dev"}\n', encoding="utf-8")
    env_file.write_text(
        "\n".join(
            [
                "AUTH0_DOMAIN=example.auth0.com",
                "AUTH0_CLIENT_ID=client_id",
                "AUTH0_CLIENT_SECRET=client_secret",
                "AUTH0_ALLOW_DELETE=true",
                'AUTH0_INCLUDED_ONLY=["tenant","resourceServers","clients","clientGrants"]',
                "AUTH0_KEYWORD_MAPPINGS_FILE=tmp/dev.json",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_auth0_deploy_cli, "_repo_root", lambda: tmp_path)

    try:
        run_auth0_deploy_cli._build_base_env(env_file)
    except ValueError as exc:
        assert "AUTH0_ALLOW_DELETE must be 'false'" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_build_base_env_rejects_invalid_included_only_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_file = tmp_path / "dev.env"
    mapping_dir = tmp_path / "tmp"
    mapping_dir.mkdir()
    (mapping_dir / "dev.json").write_text('{"ENV":"dev"}\n', encoding="utf-8")
    env_file.write_text(
        "\n".join(
            [
                "AUTH0_DOMAIN=example.auth0.com",
                "AUTH0_CLIENT_ID=client_id",
                "AUTH0_CLIENT_SECRET=client_secret",
                "AUTH0_ALLOW_DELETE=false",
                "AUTH0_INCLUDED_ONLY=tenant,clients",
                "AUTH0_KEYWORD_MAPPINGS_FILE=tmp/dev.json",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_auth0_deploy_cli, "_repo_root", lambda: tmp_path)

    try:
        run_auth0_deploy_cli._build_base_env(env_file)
    except ValueError as exc:
        assert "AUTH0_INCLUDED_ONLY must be valid JSON" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_build_base_env_rejects_unexpected_included_only_list(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_file = tmp_path / "dev.env"
    mapping_dir = tmp_path / "tmp"
    mapping_dir.mkdir()
    (mapping_dir / "dev.json").write_text('{"ENV":"dev"}\n', encoding="utf-8")
    env_file.write_text(
        "\n".join(
            [
                "AUTH0_DOMAIN=example.auth0.com",
                "AUTH0_CLIENT_ID=client_id",
                "AUTH0_CLIENT_SECRET=client_secret",
                "AUTH0_ALLOW_DELETE=false",
                'AUTH0_INCLUDED_ONLY=["tenant","clients"]',
                "AUTH0_KEYWORD_MAPPINGS_FILE=tmp/dev.json",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_auth0_deploy_cli, "_repo_root", lambda: tmp_path)

    try:
        run_auth0_deploy_cli._build_base_env(env_file)
    except ValueError as exc:
        assert "AUTH0_INCLUDED_ONLY must equal" in str(exc)
    else:
        raise AssertionError("expected ValueError")
