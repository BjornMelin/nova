"""Safe wrapper around Auth0 Deploy CLI for Nova tenant operations."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from scripts.release.validate_auth0_contract import (
    enforce_non_destructive_env_contract,
    parse_env_file,
)

_DEPLOY_CLI_SPEC = "auth0-deploy-cli@8.30.0"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_base_env(env_file: Path) -> dict[str, str]:
    raw = parse_env_file(env_file)
    required = {
        "AUTH0_DOMAIN",
        "AUTH0_CLIENT_ID",
        "AUTH0_CLIENT_SECRET",
        "AUTH0_ALLOW_DELETE",
        "AUTH0_INCLUDED_ONLY",
        "AUTH0_KEYWORD_MAPPINGS_FILE",
    }
    missing = sorted(required.difference(raw))
    if missing:
        raise ValueError(
            "env file is missing required keys: " + ", ".join(missing)
        )
    enforce_non_destructive_env_contract(raw)
    base_env = os.environ.copy()
    for key in [
        "AUTH0_DOMAIN",
        "AUTH0_CLIENT_ID",
        "AUTH0_CLIENT_SECRET",
        "AUTH0_ALLOW_DELETE",
        "AUTH0_INCLUDED_ONLY",
    ]:
        base_env[key] = raw[key]

    mapping_path = (_repo_root() / raw["AUTH0_KEYWORD_MAPPINGS_FILE"]).resolve()
    base_env["AUTH0_KEYWORD_REPLACE_MAPPINGS"] = mapping_path.read_text(
        encoding="utf-8"
    )
    return base_env


def run_import(*, env_file: Path, input_file: Path) -> int:
    """Run Deploy CLI import using one local tenant overlay."""
    env = _build_base_env(env_file)
    env["AUTH0_INPUT_FILE"] = str(input_file)
    command = [
        "npx",
        "--yes",
        _DEPLOY_CLI_SPEC,
        "import",
        f"--input_file={input_file}",
    ]
    return subprocess.run(  # noqa: S603
        command,
        cwd=_repo_root(),
        env=env,
        check=False,
    ).returncode


def run_export(*, env_file: Path, output_folder: Path) -> int:
    """Run Deploy CLI export from a temp working directory."""
    env = _build_base_env(env_file)
    env.pop("AUTH0_INPUT_FILE", None)
    output_folder.mkdir(parents=True, exist_ok=True)
    command = [
        "npx",
        "--yes",
        _DEPLOY_CLI_SPEC,
        "export",
        "--format=yaml",
        f"--output_folder={output_folder}",
    ]
    # Run from the output directory so Deploy CLI cannot overwrite repo files.
    return subprocess.run(  # noqa: S603
        command,
        cwd=output_folder,
        env=env,
        check=False,
    ).returncode


def main() -> int:
    """Run the CLI entrypoint for the safe Auth0 Deploy CLI wrapper."""
    parser = argparse.ArgumentParser(
        description="Run Auth0 Deploy CLI safely for Nova."
    )
    parser.add_argument("mode", choices=("import", "export"))
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--input-file", type=Path)
    parser.add_argument("--output-folder", type=Path)
    args = parser.parse_args()

    env_file = args.env_file.resolve()
    if args.mode == "import":
        if args.input_file is None:
            raise ValueError("--input-file is required for import")
        input_file = args.input_file.resolve()
        return run_import(env_file=env_file, input_file=input_file)

    if args.output_folder is None:
        raise ValueError("--output-folder is required for export")
    output_folder = args.output_folder.resolve()
    return run_export(env_file=env_file, output_folder=output_folder)


if __name__ == "__main__":
    raise SystemExit(main())
