#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${ROOT}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it, then run scripts/dev/install_hooks.sh." >&2
  exit 1
fi

uv run --with cfn-lint==1.46.0 cfn-lint \
  infra/nova/*.yml \
  infra/nova/deploy/*.yml \
  infra/runtime/**/*.yml
uv run --with pytest pytest -q \
  tests/infra/test_absorbed_infra_contracts.py \
  tests/infra/test_workflow_productization_contracts.py \
  tests/infra/test_workflow_contract_docs.py \
  tests/infra/test_docs_authority_contracts.py
