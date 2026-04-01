#!/usr/bin/env python3
"""Generate committed TypeScript and R SDK artifacts from canonical OpenAPI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.release.r_sdk import generate_or_check_r_sdk
from scripts.release.sdk_common import TARGETS, _load_spec
from scripts.release.typescript_sdk import generate_or_check_typescript_sdk


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for generated client management."""
    parser = argparse.ArgumentParser(
        description="Generate public TS/R SDK artifacts from OpenAPI.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated outputs are stale.",
    )
    return parser.parse_args()


def _generate_target(*, check: bool) -> list[str]:
    issues: list[str] = []
    for target in TARGETS:
        spec = _load_spec(target.spec_path)
        issues.extend(
            generate_or_check_typescript_sdk(
                target,
                spec=spec,
                check=check,
            )
        )
        issues.extend(generate_or_check_r_sdk(target, check=check))
    return issues


def main() -> int:
    """Generate SDK artifacts or fail when committed artifacts drift."""
    args = parse_args()
    issues = _generate_target(check=args.check)

    if issues:
        for issue in issues:
            print(issue)
        return 1

    message = (
        "generated client artifacts are current"
        if args.check
        else "generated client artifacts updated"
    )
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
