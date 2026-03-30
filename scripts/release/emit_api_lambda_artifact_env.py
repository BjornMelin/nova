"""Emit shell exports for the API Lambda artifact manifest."""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

_REQUIRED_FIELDS = {
    "artifact_bucket": "API_LAMBDA_ARTIFACT_BUCKET",
    "artifact_key": "API_LAMBDA_ARTIFACT_KEY",
    "artifact_sha256": "API_LAMBDA_ARTIFACT_SHA256",
}


def _load_manifest(path: Path) -> dict[str, Any]:
    """Load one API Lambda artifact manifest from disk.

    Args:
        path: Absolute path to the manifest JSON file.

    Returns:
        Parsed manifest payload.

    Raises:
        TypeError: If the manifest root payload is not a JSON object.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("API Lambda artifact manifest must be a JSON object.")
    return payload


def main() -> int:
    """Print shell-safe exports for CDK artifact inputs.

    Returns:
        Zero when the manifest is valid and all exports were emitted.

    Raises:
        ValueError: If a required manifest field is missing or blank.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-path", required=True)
    args = parser.parse_args()

    manifest = _load_manifest(Path(args.manifest_path).resolve())
    for field_name, env_var in _REQUIRED_FIELDS.items():
        value = manifest.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing required manifest field: {field_name}")
        print(f"export {env_var}={shlex.quote(value.strip())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
