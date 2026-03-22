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

uv lock --check
uv run ruff check .
uv run ruff check . --select I
uv run ruff format . --check
uv run ty check --force-exclude --error-on-warning --output-format concise \
  "${ROOT}/packages" "${ROOT}/scripts"
uv run mypy
uv run pytest -q \
  packages/nova_file_api/tests/test_runtime_security_reliability_gates.py \
  packages/nova_file_api/tests/test_auth.py::test_local_auth_error_maps_common_jwt_claim_failures \
  packages/nova_file_api/tests/test_auth.py::test_required_scope_is_enforced_from_principal_claims \
  packages/nova_file_api/tests/test_container_config.py::test_runtime_state_requires_sqs_queue_url_when_jobs_enabled \
  packages/nova_file_api/tests/test_jobs.py::test_enqueue_failure_is_not_idempotency_cached \
  packages/nova_file_api/tests/test_jobs.py::test_job_service_update_result_rejects_invalid_transition \
  packages/nova_file_api/tests/test_jobs_dynamo.py::test_dynamo_job_repository_update_if_status_enforces_expected_state \
  packages/nova_file_api/tests/test_activity_dynamo.py::test_dynamo_activity_store_uses_conditional_first_seen_markers
uv run pytest -q \
  --deselect=packages/nova_file_api/tests/test_auth.py::test_local_auth_error_maps_common_jwt_claim_failures \
  --deselect=packages/nova_file_api/tests/test_auth.py::test_required_scope_is_enforced_from_principal_claims \
  --deselect=packages/nova_file_api/tests/test_container_config.py::test_runtime_state_requires_sqs_queue_url_when_jobs_enabled \
  --deselect=packages/nova_file_api/tests/test_jobs.py::test_enqueue_failure_is_not_idempotency_cached \
  --deselect=packages/nova_file_api/tests/test_jobs.py::test_job_service_update_result_rejects_invalid_transition \
  --deselect=packages/nova_file_api/tests/test_jobs_dynamo.py::test_dynamo_job_repository_update_if_status_enforces_expected_state \
  --deselect=packages/nova_file_api/tests/test_activity_dynamo.py::test_dynamo_activity_store_uses_conditional_first_seen_markers \
  --ignore=packages/nova_file_api/tests/test_runtime_security_reliability_gates.py \
  --ignore=packages/nova_file_api/tests/test_generated_client_smoke.py
uv run pytest -q packages/nova_file_api/tests/test_generated_client_smoke.py
uv run python scripts/contracts/export_openapi.py --check
uv run python scripts/release/generate_runtime_config_contract.py --check
uv run python scripts/release/generate_clients.py --check
uv run python scripts/release/generate_python_clients.py --check
bash scripts/checks/verify_canonical_route_policy.sh

for package in \
  packages/nova_file_api \
  packages/nova_dash_bridge \
  packages/nova_runtime_support; do
  uv build "${package}"
done
