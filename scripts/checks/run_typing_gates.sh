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
  raw_scopes=("$@")
elif [ -n "${TYPING_GATES_SCOPES:-}" ]; then
  # shellcheck disable=SC2206
  raw_scopes=(${TYPING_GATES_SCOPES})
else
  raw_scopes=("packages" "scripts")
fi

ty_scopes=()
for scope in "${raw_scopes[@]}"; do
  if [ -z "${scope}" ]; then
    continue
  fi

  if [[ "${scope}" = /* ]]; then
    candidate="${scope}"
  else
    candidate="${ROOT}/${scope}"
  fi

  if [ -e "${candidate}" ]; then
    ty_scopes+=("${candidate}")
  fi
done

if [ "${#ty_scopes[@]}" -eq 0 ]; then
  ty_scopes=("${ROOT}/packages" "${ROOT}/scripts")
fi

uv run ty check --force-exclude --error-on-warning --output-format concise "${ty_scopes[@]}"
uv run mypy
