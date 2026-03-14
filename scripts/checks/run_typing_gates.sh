#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT=""
if ! ROOT="$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel 2>/dev/null)"; then
  ROOT=""
fi
ROOT="${ROOT:-$(cd -- "${SCRIPT_DIR}/../.." && pwd)}"
cd "${ROOT}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it, then run scripts/dev/install_hooks.sh." >&2
  exit 1
fi

if [ "$#" -gt 0 ]; then
  ty_scopes=("$@")
elif [ -n "${TYPING_GATES_SCOPES:-}" ]; then
  # shellcheck disable=SC2206
  ty_scopes=(${TYPING_GATES_SCOPES})
else
  ty_scopes=(packages scripts)
fi

uv run ty check --force-exclude --error-on-warning --output-format concise "${ty_scopes[@]}"
uv run mypy
