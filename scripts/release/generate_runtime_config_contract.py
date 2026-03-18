#!/usr/bin/env python3
"""Generate and verify committed runtime-config contract artifacts."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


PathFactory = Callable[[], Path]
RenderFactory = Callable[[], str]


@dataclass(frozen=True)
class ContractHelpers:
    """Typed handles for the runtime-config contract render helpers."""

    contract_json_path: PathFactory
    contract_markdown_path: PathFactory
    render_contract_json: RenderFactory
    render_contract_markdown: RenderFactory


def _load_contract_helpers() -> ContractHelpers:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from scripts.release.runtime_config_contract import (
        contract_json_path,
        contract_markdown_path,
        render_contract_json,
        render_contract_markdown,
    )

    return ContractHelpers(
        contract_json_path=contract_json_path,
        contract_markdown_path=contract_markdown_path,
        render_contract_json=render_contract_json,
        render_contract_markdown=render_contract_markdown,
    )


def _sync_artifact(path: Path, content: str, *, check: bool) -> int:
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if check:
        if existing != content:
            print(f"Runtime config contract drift detected: {path}")
            return 1
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    if existing != content:
        path.write_text(content, encoding="utf-8")
        print(f"updated {path}")
    else:
        print(f"unchanged {path}")
    return 0


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Fail when committed contract artifacts differ from generated "
            "output."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """Generate or verify the committed runtime-config contract artifacts."""
    helpers = _load_contract_helpers()
    args = _args()
    status = 0
    status |= _sync_artifact(
        helpers.contract_json_path(),
        helpers.render_contract_json(),
        check=args.check,
    )
    status |= _sync_artifact(
        helpers.contract_markdown_path(),
        helpers.render_contract_markdown(),
        check=args.check,
    )
    return status


if __name__ == "__main__":
    sys.exit(main())
