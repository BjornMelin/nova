"""Repo-local CodeArtifact npm configuration helpers."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from pathlib import Path

DEFAULT_REGION = "us-east-1"
DEFAULT_DOMAIN = "cral"
DEFAULT_REPOSITORY = "galaxypy-staging"
AWS_CLI_TIMEOUT_SECONDS = 30


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
    try:
        result = subprocess.run(
            ["aws", *args],
            check=True,
            text=True,
            capture_output=True,
            timeout=AWS_CLI_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "AWS CLI timed out while resolving CodeArtifact npm metadata"
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(stderr or str(exc)) from exc
    return result.stdout.strip()


def get_repository_endpoint() -> str:
    """Return the repo-scoped npm endpoint for the staging repository.

    Returns:
        Repository endpoint URL with a trailing slash.

    Raises:
        RuntimeError: If the AWS CLI call fails or times out.
    """
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
    """Return a CodeArtifact authorization token for npm commands.

    Returns:
        Authorization token string for npm authentication.

    Raises:
        RuntimeError: If the AWS CLI call fails or times out.
    """
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
    """Write a repo-local npmrc that scopes `@nova` to CodeArtifact.

    Returns:
        Path to the generated repo-local npm configuration file.

    Raises:
        OSError: If the file cannot be written or chmod fails.
        RuntimeError: If CodeArtifact endpoint/token lookup fails.
    """
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
    npmrc_path.chmod(0o600)
    return npmrc_path


def parse_args() -> argparse.Namespace:
    """Parse the CLI command selector.

    Returns:
        Parsed CLI namespace containing the requested command.

    Raises:
        SystemExit: If CLI arguments are invalid.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("endpoint", "env", "token"))
    return parser.parse_args()


def main() -> int:
    """Run the requested helper command and print shell-safe output.

    Returns:
        Process exit status code.

    Raises:
        RuntimeError: If CodeArtifact metadata resolution fails.
    """
    args = parse_args()
    if args.command == "endpoint":
        print(get_repository_endpoint())
        return 0
    if args.command == "token":
        print(get_authorization_token())
        return 0

    npmrc_path = write_repo_local_npmrc()
    print(f"export NPM_CONFIG_USERCONFIG={shlex.quote(str(npmrc_path))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
