#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${ROOT}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but is not on PATH." >&2
  echo "Install uv, then rerun scripts/dev/install_hooks.sh." >&2
  exit 1
fi

uv sync --locked
uv run pre-commit install --install-hooks \
  --hook-type pre-commit \
  --hook-type pre-push
