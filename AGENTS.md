# AGENTS.md (nova)

Nova is now in the **canonical wave-2 serverless baseline**.

Use this file to keep active authority small and explicit.

## Read in order

1. `docs/README.md`
2. `docs/architecture/README.md`
3. `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
4. `README.md`
5. `docs/standards/README.md`
6. `docs/runbooks/README.md`
7. `docs/plan/GREENFIELD-WAVE-2-EXECUTION.md`
8. `docs/plan/PLAN.md` for program-history context only

## Active canonical authority

The active implementation and operating baseline is the same canonical system:

- bearer JWT only
- explicit export workflow resources under `/v1/exports`
- DynamoDB-backed idempotency/state
- Regional REST API + repo-owned Lambda entrypoint + Step Functions Standard
- unified SDK package layout for TypeScript, Python, and R
- `infra/nova_cdk` as the only active infrastructure implementation surface

Primary active authority:

- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `docs/architecture/adr/ADR-0034-eliminate-auth-service-and-session-auth.md`
- `docs/architecture/adr/ADR-0035-replace-generic-jobs-with-export-workflows.md`
- `docs/architecture/adr/ADR-0036-dynamodb-idempotency-no-redis.md`
- `docs/architecture/adr/ADR-0037-sdk-generation-consolidation.md`
- `docs/architecture/adr/ADR-0038-docs-authority-reset.md`
- `docs/architecture/spec/SPEC-0027-public-api-v2.md`
- `docs/architecture/spec/SPEC-0028-export-workflow-state-machine.md`
- `docs/architecture/spec/SPEC-0029-platform-serverless.md`
- `docs/architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `docs/architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`
- `docs/contracts/deploy-output-authority-v2.schema.json`
- `docs/contracts/workflow-post-deploy-validate.schema.json`
- `docs/runbooks/release/release-runbook.md`
- `infra/nova_cdk/README.md`

## Historical / superseded

Treat these as traceability only:

- `docs/history/**`
- `docs/architecture/adr/superseded/**`
- `docs/architecture/spec/superseded/**`

## Core laws

- Do not reintroduce auth-service, session-auth, generic-job, Redis, ECS/Fargate, or split-SDK assumptions into active code, CI, docs, or release workflows.
- Keep `infra/nova_cdk` as the only active infrastructure path.
- Keep package release automation aligned to the unified package graph only.
- Keep the public API Lambda packaging flow in `reusable-release-apply.yml`; CDK must consume explicit `API_LAMBDA_ARTIFACT_BUCKET`, `API_LAMBDA_ARTIFACT_KEY`, and `API_LAMBDA_ARTIFACT_SHA256` inputs instead of rebuilding the API package locally.
- Keep `deploy-output.json` as the only published runtime authority artifact; downstream validation and runtime consumers must derive the canonical public base URL from it instead of free-text base URL configuration.
- If code, contracts, package layout, CI, or runbooks change, update the corresponding active docs in the same branch.
- Keep `AGENTS.md`, `infra/nova_cdk/README.md`, `docs/runbooks/release/release-runbook.md`, and `docs/runbooks/provisioning/github-actions-secrets-and-vars.md` aligned when release/runtime packaging or deploy inputs change.

## Verification defaults

- Use `uv sync --locked --all-packages --all-extras --dev` for repo-wide verification. The shorter `uv sync --locked --all-extras --dev` is not the canonical Nova monorepo setup.
- For local/CI-equivalent pytest verification, prefer the split lanes from `Nova CI`:
  - `uv run pytest -q -m runtime_gate`
  - `uv run pytest -q -m "not runtime_gate and not generated_smoke"`
  - `uv run pytest -q -m generated_smoke`
- Treat the split pytest lanes above as the canonical verification shape for this repo. Do not replace them with a single `uv run pytest -q` command in docs, prompts, or checklists unless the repo explicitly re-standardizes on a monolithic lane.
- Use the repo-native CDK entrypoint:
  - `npx aws-cdk@2.1107.0 synth --app "uv run --package nova-cdk python infra/nova_cdk/app.py" ...`
- CDK synth/diff/deploy must include the full required runtime stack inputs, not just account/region/JWT/domain/cert. Always provide:
  - `hosted_zone_id`
  - `hosted_zone_name`
  - `api_lambda_artifact_bucket`
  - `api_lambda_artifact_key`
  - `api_lambda_artifact_sha256`
- The API Lambda `Code.fromBucket()` warning about missing `objectVersion` is intentionally acknowledged in `infra/nova_cdk/app.py`. Nova relies on immutable content-addressed artifact keys plus SHA256/deploy-output provenance instead of threading S3 object versions through the CDK contract.
- After runtime deploys or live AWS cleanup, rebuild or fetch the authoritative deploy-output artifact and run `scripts/release/validate_runtime_release.py` against it. Treat deploy-output-bound post-deploy validation as the source of truth for runtime version, execute-api disablement, CORS, and reserved concurrency.
