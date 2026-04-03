"""Tests for persisting local Auth0 env overlays."""

from __future__ import annotations

import argparse
import stat
from pathlib import Path

import pytest

from scripts.release import persist_auth0_env


def test_write_env_file_requires_supported_environment() -> None:
    try:
        secret = "".join(["d", "e", "f"])
        persist_auth0_env.write_env_file(
            environment="prod",
            domain="example.auth0.com",
            client_id="abc",
            client_secret=secret,
        )
    except ValueError as exc:
        assert "environment must be one of" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_write_env_file_writes_restricted_permissions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo_root = tmp_path
    env_dir = repo_root / "infra" / "auth0" / "env"
    mapping_dir = repo_root / "infra" / "auth0" / "mappings"
    env_dir.mkdir(parents=True)
    mapping_dir.mkdir(parents=True)
    (mapping_dir / "dev.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(persist_auth0_env, "_repo_root", lambda: repo_root)
    monkeypatch.setattr(
        persist_auth0_env,
        "_assert_gitignored",
        lambda path: None,
    )

    secret = "".join(["d", "e", "f"])
    env_path = persist_auth0_env.write_env_file(
        environment="dev",
        domain="example.auth0.com",
        client_id="abc",
        client_secret=secret,
    )

    payload = env_path.read_text(encoding="utf-8")
    assert "AUTH0_DOMAIN=example.auth0.com" in payload
    assert env_path.stat().st_mode & 0o777 == stat.S_IRUSR | stat.S_IWUSR


def test_resolve_client_secret_from_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH0_SECRET_REF", "secret-from-env")
    env_var_name = "AUTH0_SECRET_REF"
    args = argparse.Namespace(
        client_secret=None,
        client_secret_env_var=env_var_name,
        client_secret_stdin=False,
        prompt_client_secret=False,
    )

    assert persist_auth0_env._resolve_client_secret(args) == "secret-from-env"


def test_resolve_existing_values_from_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / "dev.env"
    env_file.write_text(
        "\n".join(
            [
                "AUTH0_DOMAIN=example.auth0.com",
                "AUTH0_CLIENT_ID=client-id",
                "AUTH0_CLIENT_SECRET=secret-value",
                "",
            ]
        ),
        encoding="utf-8",
    )
    args = argparse.Namespace(
        client_secret=None,
        client_secret_env_var=None,
        client_secret_stdin=False,
        prompt_client_secret=False,
        from_env_file=str(env_file),
    )

    assert (
        persist_auth0_env._resolve_existing_value(
            explicit_value=None,
            from_env_file=str(env_file),
            key="AUTH0_DOMAIN",
        )
        == "example.auth0.com"
    )
    assert persist_auth0_env._resolve_client_secret(args) == "secret-value"
