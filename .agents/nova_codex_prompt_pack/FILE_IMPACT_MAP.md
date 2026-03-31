# File impact map

This is the recommended prompt-to-file ownership map. It is intentionally explicit so each Codex session knows what it must touch.

## Prompt 01 — Public ingress hard cut
Directly owns:
- `infra/nova_cdk/app.py`
- `infra/nova_cdk/README.md`
- `infra/nova_cdk/src/nova_cdk/__init__.py`
- `infra/nova_cdk/src/nova_cdk/serverless_stack.py` (delete or convert to compatibility-free wrapper only if strictly necessary)
- new modular CDK files under `infra/nova_cdk/src/nova_cdk/` such as:
  - `runtime_stack.py`
  - `data_plane.py`
  - `ingress.py` or equivalent
- `tests/infra/test_serverless_stack_contracts.py` (replace or split)
- new infra tests such as:
  - `tests/infra/test_runtime_stack_contracts.py`
  - `tests/infra/test_ingress_contracts.py`
- targeted architecture docs that would otherwise remain false immediately after the ingress change

## Prompt 02 — Runtime simplification, native Lambda handler, CORS, auth cleanup
Directly owns:
- `packages/nova_file_api/pyproject.toml`
- `packages/nova_file_api/src/nova_file_api/app.py`
- `packages/nova_file_api/src/nova_file_api/main.py`
- `packages/nova_file_api/src/nova_file_api/config.py`
- `packages/nova_file_api/src/nova_file_api/auth.py`
- `packages/nova_file_api/src/nova_file_api/dependencies.py` if handler/runtime init changes require it
- `packages/nova_file_api/src/nova_file_api/routes/platform.py`
- new `packages/nova_file_api/src/nova_file_api/lambda_handler.py`
- `apps/nova_file_api_service/Dockerfile` (delete, replace, or demote to non-production use)
- matching infra files from Prompt 01 if the Lambda packaging/integration changes
- new and updated API tests:
  - `packages/nova_file_api/tests/test_lambda_handler_contract.py`
  - `packages/nova_file_api/tests/test_cors_contract.py`
  - `packages/nova_file_api/tests/test_authenticated_canary_flow.py`
  - `packages/nova_file_api/tests/test_runtime_security_reliability_gates.py`
  - `packages/nova_file_api/tests/test_openapi_contract.py`

## Prompt 03 — Runtime deployment control plane and provenance
Directly owns:
- new workflows:
  - `.github/workflows/deploy-runtime.yml`
  - `.github/workflows/reusable-deploy-runtime.yml`
  - optional promotion wrappers if needed
- existing workflows:
  - `.github/workflows/post-deploy-validate.yml`
  - `.github/workflows/reusable-post-deploy-validate.yml`
  - `.github/actions/configure-aws-oidc/action.yml`
- new or updated scripts:
  - `scripts/release/resolve_deploy_output.py`
  - `scripts/release/validate_runtime_release.py`
  - `scripts/release/generate_runtime_deploy_contract.py`
- new contract schemas under `docs/contracts/`
- release / client docs tied to deploy-output authority
- matching infra workflow tests under `tests/infra/`

## Prompt 04 — Security, observability, capacity, IAM hardening
Directly owns:
- infra modules introduced in Prompt 01
- alarm and logging infrastructure
- IAM scoping helpers
- S3 lifecycle configuration
- reserved concurrency settings
- WAF rate rules and logging
- Step Functions retry policies
- infra tests covering these controls
- operator runbook sections for these controls

## Prompt 05 — Validation truth, tests, docs authority, hard-cut cleanup
Status: Completed on 2026-03-30 for `P1-5`, `P2-1` (remaining runtime-truth half), `P2-4`, and the Prompt-05-owned `P3-1` cleanup sweep.

Directly owns:
- `scripts/release/runtime_config_contract.py`
- `docs/release/runtime-config-contract.generated.md` or its replacement
- docs routers / authority maps:
  - `README.md`
  - `AGENTS.md`
  - `docs/README.md`
  - `docs/overview/ACTIVE-DOCS-INDEX.md`
  - `docs/architecture/README.md`
  - `docs/contracts/README.md`
  - `docs/runbooks/README.md`
  - `docs/clients/README.md`
  - `docs/release/README.md`
- active ADR/spec/runbook files that remain false after the implementation
- `tests/infra/test_docs_authority_contracts.py`
- `tests/infra/test_release_workflow_contracts.py`
- `tests/infra/test_workflow_contract_docs.py`
- `scripts/checks/run_infra_contracts.sh`
- post-deploy validation and canary tests

## Prompt 99 — Final critical review and finish
May touch anything left inconsistent, but should primarily:
- verify all issue IDs are closed,
- fix any remaining drift,
- run the full validation matrix,
- produce a final change report.
