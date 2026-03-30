#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${ROOT}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it, then run scripts/dev/install_hooks.sh." >&2
  exit 1
fi

uv run --with pytest pytest -q \
  tests/infra/test_ci_scope_detector.py \
  tests/infra/test_deploy_output_contracts.py \
  tests/infra/test_ingress_contracts.py \
  tests/infra/test_release_workflow_contracts.py \
  tests/infra/test_runtime_deploy_workflow_contracts.py \
  tests/infra/test_runtime_stack_contracts.py \
  tests/infra/test_workflow_contract_docs.py \
  tests/infra/test_docs_authority_contracts.py
