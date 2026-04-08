#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${ROOT}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it, then run scripts/dev/install_hooks.sh." >&2
  exit 1
fi

uv run python - <<'PY'
import sys
from pathlib import Path

from aws_cdk import App, Environment
from aws_cdk.assertions import Template

repo_root = Path.cwd()
sys.path.insert(0, str(repo_root / "infra" / "nova_cdk" / "src"))

from nova_cdk.runtime_stack import NovaRuntimeStack

context = {
    "api_domain_name": "api.dev.example.com",
    "api_lambda_artifact_bucket": "nova-ci-artifacts-111111111111-us-east-1",
    "api_lambda_artifact_key": (
        "runtime/nova-file-api/"
        "01234567-89ab-cdef-0123-456789abcdef/"
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef/"
        "nova-file-api-lambda.zip"
    ),
    "api_lambda_artifact_sha256": (
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    ),
    "workflow_lambda_artifact_bucket": "nova-ci-artifacts-111111111111-us-east-1",
    "workflow_lambda_artifact_key": (
        "runtime/nova-workflows/"
        "01234567-89ab-cdef-0123-456789abcdef/"
        "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210/"
        "nova-workflows-lambda.zip"
    ),
    "workflow_lambda_artifact_sha256": (
        "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
    ),
    "certificate_arn": (
        "arn:aws:acm:us-east-1:111111111111:"
        "certificate/12345678-1234-1234-1234-123456789012"
    ),
    "hosted_zone_id": "Z1234567890EXAMPLE",
    "hosted_zone_name": "example.com",
    "jwt_audience": "api://nova",
    "jwt_issuer": "https://issuer.example.com/",
    "jwt_jwks_url": "https://issuer.example.com/.well-known/jwks.json",
}

app = App(context=context)
stack = NovaRuntimeStack(
    app,
    "InfraContractsValidationStack",
    env=Environment(account="111111111111", region="us-east-1"),
)
template = Template.from_stack(stack).to_json()
if not template.get("Resources"):
    raise SystemExit("Synthesized runtime stack must include CloudFormation resources")
PY

uv run --with pytest pytest -q \
  tests/infra/test_cdk_module_boundaries.py \
  tests/infra/test_ci_scope_detector.py \
  tests/infra/test_deploy_output_contracts.py \
  tests/infra/test_ingress_contracts.py \
  tests/infra/test_release_control_stack_contracts.py \
  tests/infra/test_release_support_stack_contracts.py \
  tests/infra/test_release_workflow_contracts.py \
  tests/infra/test_runtime_validation_contracts.py \
  tests/infra/test_runtime_stack_contracts.py \
  tests/infra/test_security_observability_contracts.py \
  tests/infra/test_workflow_contract_docs.py \
  tests/infra/test_docs_authority_contracts.py
