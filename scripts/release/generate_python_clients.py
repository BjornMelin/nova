#!/usr/bin/env python3
"""Generate committed Python SDK package sources from canonical OpenAPI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.release.python_sdk import generate_or_check_python_sdks


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for committed Python SDK generation."""
    parser = argparse.ArgumentParser(
        description="Generate committed Python SDKs from OpenAPI.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if committed Python SDK artifacts are stale.",
    )
    return parser.parse_args()


def main() -> int:
    """Generate committed Python SDK sources or fail on drift."""
    args = parse_args()
    issues = generate_or_check_python_sdks(check=args.check)

    if issues:
        for issue in issues:
            print(issue)
        return 1

    message = (
        "generated python client artifacts are current"
        if args.check
        else "generated python client artifacts updated"
    )
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
