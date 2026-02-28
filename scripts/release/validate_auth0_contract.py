"""Validate Auth0 tenant-as-code overlay and mapping contract readiness."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TOKEN_PATTERN = re.compile(r"@@([A-Z0-9_]+)@@")
REQUIRED_ENV_KEYS = {
    "AUTH0_ALLOW_DELETE",
    "AUTH0_INPUT_FILE",
    "AUTH0_KEYWORD_MAPPINGS_FILE",
}


def extract_tokens(tenant_yaml: Path) -> set[str]:
    """Extract unique Auth0 token placeholders from tenant YAML."""
    return set(TOKEN_PATTERN.findall(tenant_yaml.read_text(encoding="utf-8")))


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a shell-style env file into key/value pairs."""
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
    """Validate one Auth0 overlay and its mapping file."""
    errors: list[str] = []
    env_values = parse_env_file(overlay_path)

    missing_keys = REQUIRED_ENV_KEYS.difference(env_values)
    for key in sorted(missing_keys):
        errors.append(f"{overlay_path}: missing required key {key}")

    allow_delete = env_values.get("AUTH0_ALLOW_DELETE")
    if allow_delete != "false":
        errors.append(
            f"{overlay_path}: AUTH0_ALLOW_DELETE must be 'false', "
            f"got {allow_delete!r}"
        )

    input_file = env_values.get("AUTH0_INPUT_FILE")
    if input_file != expected_input_file:
        errors.append(
            f"{overlay_path}: AUTH0_INPUT_FILE must be "
            f"{expected_input_file!r}, got {input_file!r}"
        )

    mapping_file_value = env_values.get("AUTH0_KEYWORD_MAPPINGS_FILE")
    if not mapping_file_value:
        return errors

    mapping_path = repo_root / mapping_file_value
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


def run_validation(repo_root: Path) -> list[str]:
    """Run Auth0 contract validation for all overlay files."""
    tenant_path = repo_root / "infra/auth0/tenant/tenant.yaml"
    required_tokens = extract_tokens(tenant_path)

    overlay_dir = repo_root / "infra/auth0/env"
    overlay_paths = sorted(overlay_dir.glob("*.env.example"))
    if not overlay_paths:
        return ["No overlay files found under infra/auth0/env"]

    errors: list[str] = []
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
    """Run CLI validation and print pass/fail summary."""
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
