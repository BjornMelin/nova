"""Validate Auth0 tenant-as-code overlay and mapping contract readiness."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

TOKEN_PATTERN = re.compile(r"@@([A-Z0-9_]+)@@")
REQUIRED_ENV_KEYS = {
    "AUTH0_ALLOW_DELETE",
    "AUTH0_INCLUDED_ONLY",
    "AUTH0_INPUT_FILE",
    "AUTH0_KEYWORD_MAPPINGS_FILE",
}
EXPECTED_MAPPING_BY_OVERLAY = {
    "dev": "infra/auth0/mappings/dev.json",
    "qa": "infra/auth0/mappings/qa.json",
    "pr": "infra/auth0/mappings/pr.json",
}
_EXAMPLE_SECRET_KEYS = {
    "AUTH0_DOMAIN",
    "AUTH0_CLIENT_ID",
    "AUTH0_CLIENT_SECRET",
}
EXPECTED_INCLUDED_ONLY = [
    "tenant",
    "resourceServers",
    "clients",
    "clientGrants",
]


def enforce_non_destructive_env_contract(env_values: dict[str, str]) -> None:
    """Validate the runtime delete/include guardrails for local overlays."""
    allow_delete = env_values.get("AUTH0_ALLOW_DELETE")
    if allow_delete != "false":
        raise ValueError(
            f"AUTH0_ALLOW_DELETE must be 'false', got {allow_delete!r}"
        )

    included_only = env_values.get("AUTH0_INCLUDED_ONLY")
    if included_only is None:
        raise ValueError("missing required key AUTH0_INCLUDED_ONLY")

    parse_included_only(included_only)


def parse_included_only(raw_value: str) -> list[str]:
    """Parse and validate the pinned Auth0 Deploy CLI include list."""
    try:
        included_only = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"AUTH0_INCLUDED_ONLY must be valid JSON: {exc}"
        ) from exc

    if not isinstance(included_only, list) or not all(
        isinstance(item, str) for item in included_only
    ):
        raise ValueError(
            "AUTH0_INCLUDED_ONLY must decode to a JSON string list"
        )
    if included_only != EXPECTED_INCLUDED_ONLY:
        raise ValueError(
            f"AUTH0_INCLUDED_ONLY must equal {EXPECTED_INCLUDED_ONLY!r}"
        )
    return included_only


def extract_tokens(tenant_yaml: Path) -> set[str]:
    """Extract unique Auth0 token placeholders from tenant YAML.

    Args:
        tenant_yaml: Path to the Auth0 tenant YAML file.

    Returns:
        Unique placeholder token names extracted from the file.

    Raises:
        OSError: If the file cannot be read.
    """
    return set(TOKEN_PATTERN.findall(tenant_yaml.read_text(encoding="utf-8")))


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a shell-style env file into key/value pairs.

    Args:
        path: Path to the env overlay file.

    Returns:
        Parsed key/value mapping from the env file.

    Raises:
        OSError: If the file cannot be read.
        ValueError: If a line is malformed or contains an empty key.
    """
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            message = f"{path}: invalid env line (missing '='): {raw_line}"
            raise ValueError(message)
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"{path}: empty env key in line: {raw_line}")
        values[key] = value.strip()
    return values


def validate_overlay(
    repo_root: Path,
    overlay_path: Path,
    expected_input_file: str,
    required_tokens: set[str],
) -> list[str]:
    """Validate one Auth0 overlay and its mapping file.

    Args:
        repo_root: Repository root path.
        overlay_path: Path to an overlay env file.
        expected_input_file: Required AUTH0_INPUT_FILE value.
        required_tokens: Token names required by tenant.yaml.

    Returns:
        Validation error messages for this overlay.
    """
    errors: list[str] = []
    try:
        env_values = parse_env_file(overlay_path)
    except (OSError, ValueError) as exc:
        return [f"{overlay_path}: unable to parse env overlay: {exc}"]

    missing_keys = REQUIRED_ENV_KEYS.difference(env_values)
    errors.extend(
        f"{overlay_path}: missing required key {key}"
        for key in sorted(missing_keys)
    )

    if (
        "AUTH0_ALLOW_DELETE" in env_values
        and "AUTH0_INCLUDED_ONLY" in env_values
    ):
        try:
            enforce_non_destructive_env_contract(env_values)
        except ValueError as exc:
            errors.append(f"{overlay_path}: {exc}")

    if "AUTH0_INPUT_FILE" in env_values:
        input_file = env_values["AUTH0_INPUT_FILE"]
        if input_file != expected_input_file:
            errors.append(
                f"{overlay_path}: AUTH0_INPUT_FILE must be "
                f"{expected_input_file!r}, got {input_file!r}"
            )

    for key in sorted(_EXAMPLE_SECRET_KEYS):
        value = env_values.get(key)
        if not value:
            errors.append(f"{overlay_path}: missing required example key {key}")
            continue
        if not value.startswith("REPLACE_WITH_"):
            errors.append(
                f"{overlay_path}: {key} must stay a REPLACE_WITH_* placeholder"
            )

    mapping_file_value = env_values.get("AUTH0_KEYWORD_MAPPINGS_FILE")
    if not mapping_file_value:
        return errors

    overlay_name = overlay_path.name.removesuffix(".env.example")
    expected_mapping_path = EXPECTED_MAPPING_BY_OVERLAY.get(overlay_name)
    if expected_mapping_path is None:
        errors.append(
            f"{overlay_path}: unknown overlay name {overlay_name!r}; "
            f"expected one of: {', '.join(sorted(EXPECTED_MAPPING_BY_OVERLAY))}"
        )
        return errors
    if mapping_file_value != expected_mapping_path:
        errors.append(
            f"{overlay_path}: AUTH0_KEYWORD_MAPPINGS_FILE must be "
            f"{expected_mapping_path!r}, got {mapping_file_value!r}"
        )

    repo_root_resolved = repo_root.resolve()
    mapping_path = (repo_root / mapping_file_value).resolve()
    try:
        mapping_path.relative_to(repo_root_resolved)
    except ValueError:
        errors.append(
            f"{overlay_path}: AUTH0_KEYWORD_MAPPINGS_FILE must stay under "
            f"repository root, got {mapping_file_value!r}"
        )
        return errors
    if not mapping_path.exists():
        errors.append(
            f"{overlay_path}: mapping file does not exist: {mapping_file_value}"
        )
        return errors

    try:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(
            f"{overlay_path}: invalid JSON in {mapping_file_value}: {exc}"
        )
        return errors

    if not isinstance(mapping, dict):
        errors.append(
            f"{overlay_path}: mapping file must contain a JSON object"
        )
        return errors

    mapping_keys = {str(key) for key in mapping}
    missing_tokens = sorted(required_tokens.difference(mapping_keys))
    if missing_tokens:
        errors.append(
            f"{overlay_path}: mapping file missing token keys: "
            f"{', '.join(missing_tokens)}"
        )

    return errors


def _tracked_env_file_errors(repo_root: Path) -> list[str]:
    """Return errors for any tracked local Auth0 env files."""
    git = shutil.which("git")
    if git is None or not (repo_root / ".git").exists():
        return []
    result = subprocess.run(  # noqa: S603
        [git, "ls-files", "infra/auth0/env"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ["unable to inspect tracked Auth0 env files with git ls-files"]
    tracked_files = [
        path
        for path in result.stdout.splitlines()
        if path.endswith(".env") and not path.endswith(".env.example")
    ]
    return [
        "tracked local Auth0 env file is forbidden: " + path
        for path in tracked_files
    ]


def run_validation(repo_root: Path) -> list[str]:
    """Run Auth0 contract validation for all overlay files.

    Args:
        repo_root: Repository root path.

    Returns:
        Aggregated validation errors across all overlays.
    """
    tenant_path = repo_root / "infra/auth0/tenant/tenant.yaml"
    try:
        required_tokens = extract_tokens(tenant_path)
    except OSError as exc:
        return [f"{tenant_path}: unable to read tenant YAML: {exc}"]

    overlay_dir = repo_root / "infra/auth0/env"
    overlay_paths = sorted(overlay_dir.glob("*.env.example"))
    if not overlay_paths:
        return ["No overlay files found under infra/auth0/env"]

    errors: list[str] = []
    errors.extend(_tracked_env_file_errors(repo_root))
    for overlay_path in overlay_paths:
        errors.extend(
            validate_overlay(
                repo_root=repo_root,
                overlay_path=overlay_path,
                expected_input_file="infra/auth0/tenant/tenant.yaml",
                required_tokens=required_tokens,
            )
        )
    return errors


def main() -> int:
    """Run CLI validation and print pass/fail summary.

    Returns:
        Zero when validation succeeds, otherwise one.
    """
    parser = argparse.ArgumentParser(
        description="Validate Auth0 tenant overlays and keyword mappings."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root path (default: inferred from script location).",
    )
    args = parser.parse_args()

    errors = run_validation(args.repo_root.resolve())
    if errors:
        print("Auth0 contract validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Auth0 contract validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
