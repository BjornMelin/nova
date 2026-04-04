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
    parser.add_argument(
        "--configured-sign-batch-size",
        type=int,
        default=None,
        help="Optional explicit sign batch size override.",
    )
    args = parser.parse_args()

    if args.max_concurrency <= 0:
        parser.error("Argument --max-concurrency must be a positive integer")
    if args.part_size_bytes <= 0:
        parser.error("Argument --part-size-bytes must be a positive integer")

    scenarios = []
    try:
        sizes = parse_sizes_gib(args.sizes_gib)
    except ValueError as exc:
        parser.error(str(exc))

    for file_size_bytes in sizes:
        try:
            plan = build_browser_multipart_plan(
                file_size_bytes=file_size_bytes,
                part_size_bytes=args.part_size_bytes,
                max_concurrency=args.max_concurrency,
                configured_sign_batch_size=args.configured_sign_batch_size,
            )
        except ValueError as exc:
            parser.error(str(exc))
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
                "current_rule": (
                    "configured sign batch when provided; otherwise "
                    "min(128, max(64, 4 * maxConcurrency))"
                ),
                "scenarios": scenarios,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
