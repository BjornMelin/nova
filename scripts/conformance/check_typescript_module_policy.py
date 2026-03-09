#!/usr/bin/env python3
"""Enforce TypeScript module policy: no barrels, no index.ts entrypoints."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TS_ROOT = REPO_ROOT / "packages"
BARREL_RE = re.compile(
    r"^\s*export\s+(?:type\s+)?(?:\*|\{[^}]+\})\s+from\s+['\"]"
)


def _iter_ts_files() -> list[Path]:
    return sorted(TS_ROOT.glob("**/src/**/*.ts"))


def main() -> int:
    """Validate repository TypeScript modules follow no-barrel policy."""
    violations: list[str] = []
    for path in _iter_ts_files():
        rel = path.relative_to(REPO_ROOT)
        if path.name == "index.ts":
            violations.append(f"{rel}: index.ts is disallowed")
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            violations.append(f"{rel}: failed to read file: {exc}")
            continue
        for line_no, line in enumerate(lines, start=1):
            if BARREL_RE.match(line):
                violations.append(
                    f"{rel}:{line_no}: re-export barrel syntax is disallowed"
                )

    if violations:
        print("TypeScript module policy violations detected:")
        for item in violations:
            print(f" - {item}")
        return 1

    print("TypeScript module policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
