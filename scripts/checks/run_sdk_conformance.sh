#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${ROOT}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it, then run scripts/dev/install_hooks.sh." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required for SDK conformance checks." >&2
  exit 1
fi

if ! command -v R >/dev/null 2>&1; then
  echo "R is required for SDK conformance checks." >&2
  exit 1
fi

uv run python scripts/conformance/check_typescript_module_policy.py
npm run -w @nova/sdk typecheck
npm run -w @nova/sdk build
npm run -w @nova/contracts-ts-conformance typecheck
npm run -w @nova/contracts-ts-conformance verify
uv run python scripts/release/generate_clients.py --check
uv run pytest -q scripts/release/tests/test_typescript_sdk_contracts.py

bash scripts/checks/verify_r_cmd_check.sh packages/nova_sdk_r_file
