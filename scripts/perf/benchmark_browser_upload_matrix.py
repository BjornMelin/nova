"""Benchmark the current browser multipart batching behavior."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.perf.file_transfer_observability_baseline import (
    CURRENT_MAX_CONCURRENCY,
    CURRENT_PART_SIZE_BYTES,
    build_browser_multipart_plan,
    bytes_text,
    parse_sizes_gib,
)


def main() -> None:
    """Render the current browser multipart batching matrix as JSON."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sizes-gib",
        default="5,50,500,1024",
        help="Comma-separated file sizes in GiB.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=CURRENT_MAX_CONCURRENCY,
        help="Concurrency value to feed into the current browser batch rule.",
    )
    parser.add_argument(
        "--part-size-bytes",
        type=int,
        default=CURRENT_PART_SIZE_BYTES,
        help="Multipart part size in bytes.",
    )
    args = parser.parse_args()

    scenarios = []
    for file_size_bytes in parse_sizes_gib(args.sizes_gib):
        plan = build_browser_multipart_plan(
            file_size_bytes=file_size_bytes,
            part_size_bytes=args.part_size_bytes,
            max_concurrency=args.max_concurrency,
        )
        scenarios.append(
            {
                "file_size_bytes": plan.file_size_bytes,
                "file_size_human": bytes_text(plan.file_size_bytes),
                "part_size_bytes": plan.part_size_bytes,
                "part_size_human": bytes_text(plan.part_size_bytes),
                "max_concurrency": plan.max_concurrency,
                "sign_batch_size": plan.sign_batch_size,
                "total_parts": plan.total_parts,
                "sign_requests": plan.sign_requests,
            }
        )

    print(
        json.dumps(
            {
                "mode": "browser_upload_batch_matrix",
                "current_rule": "min(16, max(1, 2 * maxConcurrency))",
                "scenarios": scenarios,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
