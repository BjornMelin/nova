"""Export canonical OpenAPI artifacts for Nova runtime services."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from nova_auth_api.app import create_app as create_auth_app
from nova_file_api.app import create_app as create_file_app

OpenApiFactory = Callable[[], Any]

OPENAPI_OUTPUTS: dict[str, OpenApiFactory] = {
    "nova-file-api.openapi.json": create_file_app,
    "nova-auth-api.openapi.json": create_auth_app,
}
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "packages" / "contracts" / "openapi"


def _render_openapi() -> dict[str, str]:
    """Render each runtime application's OpenAPI document as JSON text."""
    rendered: dict[str, str] = {}
    for name, app_factory in OPENAPI_OUTPUTS.items():
        schema = app_factory().openapi()
        rendered[name] = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    return rendered


def _write_outputs(output_dir: Path, *, check: bool) -> int:
    """Write or verify canonical OpenAPI artifacts in the target directory."""
    rendered = _render_openapi()
    status = 0
    if not check:
        output_dir.mkdir(parents=True, exist_ok=True)
    elif not output_dir.exists():
        print(
            f"OpenAPI artifact drift detected: missing directory {output_dir}"
        )
        return 1

    for name, content in rendered.items():
        destination = output_dir / name
        existing = (
            destination.read_text(encoding="utf-8")
            if destination.exists()
            else None
        )
        if check:
            if existing != content:
                print(f"OpenAPI artifact drift detected: {destination}")
                status = 1
            continue
        if existing != content:
            destination.write_text(content, encoding="utf-8")
            print(f"updated {destination}")
        else:
            print(f"unchanged {destination}")

    if check:
        expected_files = {output_dir / name for name in rendered}
        existing_files = {
            path for path in output_dir.glob("*.openapi.json") if path.is_file()
        }
        for extra in sorted(existing_files - expected_files):
            print(f"OpenAPI artifact drift detected: unexpected file {extra}")
            status = 1

    return status


def _args() -> argparse.Namespace:
    """Parse command-line options for OpenAPI export/check workflows."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when committed artifacts differ from the runtime export.",
    )
    return parser.parse_args()


def main() -> int:
    """Render canonical OpenAPI documents to the configured output path."""
    args = _args()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = REPO_ROOT / output_dir
    return _write_outputs(output_dir, check=args.check)


if __name__ == "__main__":
    sys.exit(main())
