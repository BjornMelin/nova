#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${ROOT}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it, then run scripts/dev/install_hooks.sh." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for release image builds." >&2
  exit 1
fi

if ! docker buildx version >/dev/null 2>&1; then
  echo "docker buildx is required for release image builds." >&2
  exit 1
fi

docker buildx build --load \
  -f apps/nova_file_api_service/Dockerfile \
  -t nova-file-api:test .
docker buildx build --load \
  -f apps/nova_auth_api_service/Dockerfile \
  -t nova-auth-api:test .
uv run pytest -q \
  packages/nova_file_api/tests/test_runtime_security_reliability_gates.py \
  tests/infra/test_workflow_productization_contracts.py \
  tests/infra/test_workflow_contract_docs.py \
  tests/infra/test_docs_authority_contracts.py
