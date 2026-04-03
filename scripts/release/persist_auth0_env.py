"""Persist local gitignored Auth0 tenant credentials for one environment."""

from __future__ import annotations

import argparse
import getpass
import os
import shutil
import stat
import subprocess
from pathlib import Path

from scripts.release.validate_auth0_contract import parse_env_file

_SUPPORTED_ENVIRONMENTS = {"dev", "pr", "qa"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _assert_gitignored(path: Path) -> None:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to validate local env safety")
    result = subprocess.run(  # noqa: S603
        [git, "check-ignore", str(path)],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"{path} is not gitignored")


def write_env_file(
    *,
    environment: str,
    domain: str,
    client_id: str,
    client_secret: str,
) -> Path:
    """Write one local Auth0 env file with restrictive permissions.

    Args:
        environment: Target overlay environment (`dev`, `qa`, or `pr`).
        domain: Auth0 tenant domain.
        client_id: Auth0 machine-to-machine client id.
        client_secret: Auth0 machine-to-machine client secret.

    Returns:
        Path to the persisted local env file.

    Raises:
        ValueError: If environment is unsupported or path is not gitignored.
        FileNotFoundError: If the environment mapping file does not exist.
    """
    if environment not in _SUPPORTED_ENVIRONMENTS:
        raise ValueError(
            "environment must be one of: "
            + ", ".join(sorted(_SUPPORTED_ENVIRONMENTS))
        )

    repo_root = _repo_root()
    env_path = repo_root / "infra" / "auth0" / "env" / f"{environment}.env"
    mapping_path = (
        repo_root / "infra" / "auth0" / "mappings" / f"{environment}.json"
    )
    _assert_gitignored(env_path)
    if not mapping_path.exists():
        raise FileNotFoundError(mapping_path)

    payload = "\n".join(
        [
            f"AUTH0_DOMAIN={domain}",
            f"AUTH0_CLIENT_ID={client_id}",
            f"AUTH0_CLIENT_SECRET={client_secret}",
            "AUTH0_ALLOW_DELETE=false",
            (
                'AUTH0_INCLUDED_ONLY=["tenant","resourceServers","clients",'
                '"clientGrants"]'
            ),
            "AUTH0_INPUT_FILE=infra/auth0/tenant/tenant.yaml",
            (
                "AUTH0_KEYWORD_MAPPINGS_FILE="
                f"infra/auth0/mappings/{environment}.json"
            ),
            "",
        ]
    )
    env_path.write_text(payload, encoding="utf-8")
    env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return env_path


def _resolve_client_secret(args: argparse.Namespace) -> str:
    """Resolve the client secret from one explicit secure input source."""
    if args.client_secret is not None:
        return str(args.client_secret)
    if args.client_secret_env_var is not None:
        try:
            return os.environ[args.client_secret_env_var]
        except KeyError as exc:  # pragma: no cover - defensive
            raise ValueError(
                "client secret env var is not set: "
                f"{args.client_secret_env_var}"
            ) from exc
    if args.client_secret_stdin:
        return input()
    if args.prompt_client_secret:
        return getpass.getpass("Auth0 client secret: ")
    if args.from_env_file is not None:
        existing = parse_env_file(Path(args.from_env_file))
        try:
            return existing["AUTH0_CLIENT_SECRET"]
        except KeyError as exc:
            raise ValueError(
                f"{args.from_env_file}: missing AUTH0_CLIENT_SECRET"
            ) from exc
    raise ValueError("one client secret source must be provided")


def _resolve_existing_value(
    *,
    explicit_value: str | None,
    from_env_file: str | None,
    key: str,
) -> str:
    """Resolve one value from an explicit flag or an existing local env file."""
    if explicit_value is not None:
        return explicit_value
    if from_env_file is None:
        raise ValueError(f"{key.lower().replace('_', '-')} is required")
    existing = parse_env_file(Path(from_env_file))
    try:
        return existing[key]
    except KeyError as exc:
        raise ValueError(f"{from_env_file}: missing {key}") from exc


def main() -> int:
    """Run the CLI entrypoint for persisting one local Auth0 env file."""
    parser = argparse.ArgumentParser(
        description="Persist a local gitignored Auth0 env file."
    )
    parser.add_argument("--environment", required=True)
    parser.add_argument("--domain")
    parser.add_argument("--client-id")
    parser.add_argument("--from-env-file")
    secret_group = parser.add_mutually_exclusive_group(required=False)
    secret_group.add_argument("--client-secret")
    secret_group.add_argument("--client-secret-env-var")
    secret_group.add_argument(
        "--client-secret-stdin",
        action="store_true",
    )
    secret_group.add_argument(
        "--prompt-client-secret",
        action="store_true",
    )
    args = parser.parse_args()
    domain = _resolve_existing_value(
        explicit_value=args.domain,
        from_env_file=args.from_env_file,
        key="AUTH0_DOMAIN",
    )
    client_id = _resolve_existing_value(
        explicit_value=args.client_id,
        from_env_file=args.from_env_file,
        key="AUTH0_CLIENT_ID",
    )
    client_secret = _resolve_client_secret(args)

    env_path = write_env_file(
        environment=args.environment,
        domain=domain,
        client_id=client_id,
        client_secret=client_secret,
    )
    print(env_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
