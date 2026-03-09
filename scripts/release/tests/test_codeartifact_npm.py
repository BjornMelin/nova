"""Tests for repo-local CodeArtifact npm helper commands."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.release import codeartifact_npm


def test_endpoint_and_repo_local_npmrc_use_env_overrides(
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

    endpoint = codeartifact_npm.get_repository_endpoint()
    npmrc_path = codeartifact_npm.write_repo_local_npmrc()

    assert endpoint == (
        "https://alt-domain-111122223333.d.codeartifact.us-west-2.amazonaws.com/"
        "npm/alt-repo/"
    )
    assert npmrc_path == tmp_path / ".npmrc.codeartifact"
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
    assert calls[2] == (
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
        raise codeartifact_npm.subprocess.TimeoutExpired("aws", 30)

    monkeypatch.setattr(codeartifact_npm.subprocess, "run", _raise_timeout)

    with pytest.raises(RuntimeError, match="timed out"):
        codeartifact_npm._run_aws("codeartifact", "get-authorization-token")
