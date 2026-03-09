"""Repo-local CodeArtifact npm configuration helpers."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

DEFAULT_REGION = "us-east-1"
DEFAULT_DOMAIN = "cral"
DEFAULT_REPOSITORY = "galaxypy-staging"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _region() -> str:
    return (
        os.environ.get("AWS_REGION")
        or os.environ.get("NOVA_CODEARTIFACT_REGION")
        or DEFAULT_REGION
    )


def _domain() -> str:
    return (
        os.environ.get("CODEARTIFACT_DOMAIN")
        or os.environ.get("NOVA_CODEARTIFACT_DOMAIN")
        or DEFAULT_DOMAIN
    )


def _repository() -> str:
    return (
        os.environ.get("CODEARTIFACT_STAGING_REPOSITORY")
        or os.environ.get("NOVA_CODEARTIFACT_NPM_REPOSITORY")
        or DEFAULT_REPOSITORY
    )


def _run_aws(*args: str) -> str:
    result = subprocess.run(
        ["aws", *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def get_repository_endpoint() -> str:
    """Return the npm endpoint for the configured CodeArtifact repository."""
    endpoint = _run_aws(
        "codeartifact",
        "get-repository-endpoint",
        "--domain",
        _domain(),
        "--repository",
        _repository(),
        "--format",
        "npm",
        "--region",
        _region(),
        "--query",
        "repositoryEndpoint",
        "--output",
        "text",
    )
    return endpoint.rstrip("/") + "/"


def get_authorization_token() -> str:
    """Return a temporary CodeArtifact auth token for npm operations."""
    return _run_aws(
        "codeartifact",
        "get-authorization-token",
        "--domain",
        _domain(),
        "--region",
        _region(),
        "--query",
        "authorizationToken",
        "--output",
        "text",
    )


def write_repo_local_npmrc() -> Path:
    """Write a repo-local npmrc for the configured CodeArtifact repository."""
    repo_root = _repo_root()
    endpoint = get_repository_endpoint()
    token = get_authorization_token()
    endpoint_host = endpoint.removeprefix("https://")
    npmrc_path = repo_root / ".npmrc.codeartifact"
    npmrc_path.write_text(
        "\n".join(
            [
                "registry=https://registry.npmjs.org/",
                f"@nova:registry={endpoint}",
                f"//{endpoint_host}:_authToken={token}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return npmrc_path


def parse_args() -> argparse.Namespace:
    """Parse the CLI command for endpoint, env, or token output."""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("endpoint", "env", "token"))
    return parser.parse_args()


def main() -> int:
    """Execute the selected helper command and emit shell-safe output."""
    args = parse_args()
    if args.command == "endpoint":
        print(get_repository_endpoint())
        return 0
    if args.command == "token":
        print(get_authorization_token())
        return 0

    npmrc_path = write_repo_local_npmrc()
    print(f"export NPM_CONFIG_USERCONFIG='{npmrc_path}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
