"""Tests for the repo-local CodeArtifact npm helper."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.release import codeartifact_npm


def test_prepare_npm_environment_uses_env_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Helper should honor AWS env overrides and write a repo-local npmrc."""
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("CODEARTIFACT_DOMAIN", "alt-domain")
    monkeypatch.setenv("CODEARTIFACT_STAGING_REPOSITORY", "alt-repo")
    monkeypatch.setattr(codeartifact_npm, "_repo_root", lambda: tmp_path)

    calls: list[tuple[str, ...]] = []

    def fake_run_aws(*args: str) -> str:
        calls.append(args)
        if "get-repository-endpoint" in args:
            return (
                "https://alt-domain-111122223333.d.codeartifact.us-west-2."
                "amazonaws.com/npm/alt-repo/"
            )
        if "get-authorization-token" in args:
            return "token-123"
        raise AssertionError(f"unexpected aws invocation: {args!r}")

    monkeypatch.setattr(codeartifact_npm, "_run_aws", fake_run_aws)

    output_path = tmp_path / "ci" / "custom.npmrc"
    npmrc_path, endpoint = codeartifact_npm.prepare_npm_environment(
        output_path=output_path
    )

    assert endpoint == (
        "https://alt-domain-111122223333.d.codeartifact.us-west-2.amazonaws.com/"
        "npm/alt-repo/"
    )
    assert npmrc_path == output_path
    assert npmrc_path.read_text(encoding="utf-8") == (
        "registry=https://registry.npmjs.org/\n"
        "@nova:registry=https://alt-domain-111122223333.d.codeartifact.us-west-2.amazonaws.com/npm/alt-repo/\n"
        "//alt-domain-111122223333.d.codeartifact.us-west-2.amazonaws.com/npm/alt-repo/:_authToken=token-123\n"
    )
    assert calls[0] == (
        "codeartifact",
        "get-repository-endpoint",
        "--domain",
        "alt-domain",
        "--repository",
        "alt-repo",
        "--format",
        "npm",
        "--region",
        "us-west-2",
        "--query",
        "repositoryEndpoint",
        "--output",
        "text",
    )
    assert calls[1] == (
        "codeartifact",
        "get-authorization-token",
        "--domain",
        "alt-domain",
        "--region",
        "us-west-2",
        "--query",
        "authorizationToken",
        "--output",
        "text",
    )


def test_run_aws_times_out_with_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_timeout(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise subprocess.TimeoutExpired("aws", 30)

    monkeypatch.setattr(subprocess, "run", _raise_timeout)

    with pytest.raises(RuntimeError, match="timed out"):
        codeartifact_npm._run_aws("codeartifact", "get-authorization-token")


def test_helper_uses_repo_defaults_when_env_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODEARTIFACT_DOMAIN", raising=False)
    monkeypatch.delenv("CODEARTIFACT_STAGING_REPOSITORY", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)

    calls: list[tuple[str, ...]] = []

    def fake_run_aws(*args: str) -> str:
        calls.append(args)
        if "get-repository-endpoint" in args:
            return (
                "https://cral-111122223333.d.codeartifact.us-east-1."
                "amazonaws.com/npm/galaxypy-staging/"
            )
        if "get-authorization-token" in args:
            return "token-default"
        raise AssertionError(f"unexpected aws invocation: {args!r}")

    monkeypatch.setattr(codeartifact_npm, "_run_aws", fake_run_aws)

    endpoint = codeartifact_npm.get_repository_endpoint()
    authorization_value = codeartifact_npm.get_authorization_token()

    assert endpoint == (
        "https://cral-111122223333.d.codeartifact.us-east-1.amazonaws.com/"
        "npm/galaxypy-staging/"
    )
    assert authorization_value == "token-default"
    assert calls == [
        (
            "codeartifact",
            "get-repository-endpoint",
            "--domain",
            "cral",
            "--repository",
            "galaxypy-staging",
            "--format",
            "npm",
            "--region",
            "us-east-1",
            "--query",
            "repositoryEndpoint",
            "--output",
            "text",
        ),
        (
            "codeartifact",
            "get-authorization-token",
            "--domain",
            "cral",
            "--region",
            "us-east-1",
            "--query",
            "authorizationToken",
            "--output",
            "text",
        ),
    ]


def test_helper_ignores_blank_env_values_and_falls_back_to_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEARTIFACT_DOMAIN", "   ")
    monkeypatch.setenv("CODEARTIFACT_STAGING_REPOSITORY", " \t ")
    monkeypatch.setenv("AWS_REGION", "")

    assert codeartifact_npm._domain() == "cral"
    assert codeartifact_npm._repository() == "galaxypy-staging"
    assert codeartifact_npm._region() == "us-east-1"


def test_helper_ignores_legacy_repository_alias_and_uses_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODEARTIFACT_STAGING_REPOSITORY", raising=False)
    monkeypatch.setenv("CODEARTIFACT_REPOSITORY_NAME", "fallback-repo")

    assert codeartifact_npm._repository() == "galaxypy-staging"


def test_main_env_command_emits_both_exports(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "custom.npmrc"
    monkeypatch.setattr(
        codeartifact_npm,
        "parse_args",
        lambda: type(
            "Args",
            (),
            {
                "command": "env",
                "output_path": output_path,
            },
        )(),
    )
    monkeypatch.setattr(
        codeartifact_npm,
        "prepare_npm_environment",
        lambda *, output_path: (output_path, "https://example.invalid/npm/"),
    )

    assert codeartifact_npm.main() == 0
    assert capsys.readouterr().out == (
        f"export NPM_CONFIG_USERCONFIG={output_path}\n"
        "export NPM_REGISTRY_URL=https://example.invalid/npm/\n"
    )
