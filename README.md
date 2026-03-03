# nova runtime

![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-0.129%2B-009688?logo=fastapi&logoColor=white) ![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1-6BA539?logo=openapiinitiative&logoColor=white) ![AWS S3](https://img.shields.io/badge/AWS-S3-569A31?logo=amazons3&logoColor=white) ![AWS SQS](https://img.shields.io/badge/AWS-SQS-FF9900?logo=amazonaws&logoColor=white) ![Ruff](https://img.shields.io/badge/lint-ruff-D7FF64?logo=ruff&logoColor=111111) ![Mypy](https://img.shields.io/badge/types-mypy-2A6DB2?logo=python&logoColor=white) ![Pytest](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)

FastAPI control-plane service for direct-to-S3 upload/download orchestration.
The API returns presigned metadata and async job state. It never proxies file
bytes.

## Architecture State

Route authority is hard-cut canonical:

- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `docs/architecture/spec/SPEC-0000-http-api-contract.md`
- `docs/architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md`
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`

Runtime API surface is `/v1/*` plus `/metrics/summary`. Legacy `/api/*`,
`/healthz`, and `/readyz` are removed.

## Runtime Capabilities (Current Implemented)

- Transfer endpoints:
  - `POST /v1/transfers/uploads/initiate`
  - `POST /v1/transfers/uploads/sign-parts`
  - `POST /v1/transfers/uploads/complete`
  - `POST /v1/transfers/uploads/abort`
  - `POST /v1/transfers/downloads/presign`
- Async job endpoints:
  - `POST /v1/jobs`
  - `GET /v1/jobs`
  - `GET /v1/jobs/{job_id}`
  - `POST /v1/jobs/{job_id}/cancel`
  - `POST /v1/jobs/{job_id}/retry`
  - `GET /v1/jobs/{job_id}/events`
  - `POST /v1/internal/jobs/{job_id}/result` (worker/internal)
- Capability endpoints:
  - `GET /v1/capabilities`
  - `POST /v1/resources/plan`
  - `GET /v1/releases/info`
- Operational endpoints:
  - `GET /v1/health/live`
  - `GET /v1/health/ready`
  - `GET /metrics/summary`

## Production Semantics (Implemented)

### Enqueue reliability contract

- Queue publish failures are surfaced to clients.
- `POST /v1/jobs` queue publish failure returns:
  - `503 Service Unavailable`
  - `error.code = "queue_unavailable"`
- When enqueue publish fails after record creation, the job record is
  transitioned to `failed`.
- Failed enqueue attempts are not idempotency replay cached.
- In-memory queue mode honors `process_immediately`; when disabled, jobs remain
  `pending` after enqueue.

### Worker result-update contract

- `POST /v1/internal/jobs/{job_id}/result` is used by trusted worker paths.
- Worker updates must follow legal transitions:
  - `pending -> pending|running|succeeded|failed|canceled`
  - `running -> running|succeeded|failed|canceled`
  - terminal states (`succeeded|failed|canceled`) only allow idempotent
    same-state updates.
- Invalid transitions return `409` with `error.code = "conflict"`.
- `succeeded` updates always normalize `error` to `null`.

### Readiness contract

- `/v1/health/ready` reflects only critical traffic-serving dependencies.
- Feature flags such as `JOBS_ENABLED` do not affect readiness pass/fail.
- `bucket_configured` is true only when `FILE_TRANSFER_BUCKET` is non-empty
  after trimming whitespace.

## Required Configuration Rules

Startup fails fast for invalid backend selections:

- `JOBS_QUEUE_BACKEND=sqs` and `JOBS_ENABLED=true` requires
  `JOBS_SQS_QUEUE_URL`.
- `ACTIVITY_STORE_BACKEND=dynamodb` requires `ACTIVITY_ROLLUPS_TABLE`.
- Missing/blank `FILE_TRANSFER_BUCKET` keeps `/v1/health/ready` non-ready.

## Auth0 Tenant-as-Code (a0deploy)

Canonical Auth0 configuration for this repo lives in `infra/auth0/`.

- Shared resource definition: `infra/auth0/tenant/tenant.yaml`
- Environment overlays:
  - `infra/auth0/env/dev.env.example` (active local dev)
  - `infra/auth0/env/qa.env.example` (scaffold placeholder)
  - `infra/auth0/env/pr.env.example` (scaffold placeholder)
- Safety default in all overlays: `AUTH0_ALLOW_DELETE=false`

Current local-dev policy is single-tenant: use only the `dev` overlay now.
QA/PR overlays remain scaffold-only until explicit cutover.

Runbook: `docs/plan/release/AUTH0-A0DEPLOY-RUNBOOK.md`
Contract validator: `python -m scripts.release.validate_auth0_contract`

## Local Development

Run in repository root:

```bash
source .venv/bin/activate && uv lock --check
source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .
source .venv/bin/activate && uv run mypy
source .venv/bin/activate && uv run pytest -q
```

For workspace packaging metadata checks, run isolated builds:

```bash
source .venv/bin/activate && \
for p in packages/nova_file_api packages/nova_auth_api \
  packages/nova_dash_bridge apps/nova_file_api_service \
  apps/nova_auth_api_service; do uv build "$p"; done
```

## Threading and Async Workload Notes

- Sync JWT verification and FastAPI transfer adapters use AnyIO thread pools.
- Environment controls:
  - `OIDC_VERIFIER_THREAD_TOKENS` (default: `40`) for local JWT verification and
    auth API verifier work.
  - `FILE_TRANSFER_THREAD_TOKENS` (default: `80`) for synchronous transfer
    and route adapters.
- Raise these values for higher parallel verification/upload fan-out; lower them
  if you need tighter host resource usage after load testing.

## OpenAPI Contract Smoke

Generated-client smoke coverage is enforced with:

```bash
source .venv/bin/activate && \
uv run pytest -q \
  packages/nova_file_api/tests/test_generated_client_smoke.py
```

The smoke test generates a Python client with `openapi-python-client` from the
runtime OpenAPI schema and verifies generated code compiles successfully.

## Release Automation

Hybrid release model:

1. GitHub Actions currently handles CI and selective release planning/apply:
   - `.github/workflows/ci.yml`
   - `.github/workflows/conformance.yml`
   - `.github/workflows/release-plan.yml`
   - `.github/workflows/release-apply.yml`
   - `.github/workflows/verify-signature.yml`
   - `release-apply.yml` safety controls:
     - `workflow_run` execution is restricted to successful `main` runs.
     - checkout is pinned to the planned `workflow_run.head_sha`.
     - manual `workflow_dispatch` apply runs are restricted to `main`.
2. Release tooling scripts live under `scripts/release/`:
   - changed unit detection
   - deterministic version planning
   - selective version apply
   - release manifest generation
3. AWS promotion is Dev -> ManualApproval -> Prod via Nova-owned CI/CD stacks
   and templates under `infra/nova/**`, consuming immutable artifacts from the
   signed release commit.
   - Deploy marker template authority is `infra/nova/deploy/image-digest-ssm.yml`.
4. Workflow artifact state:
   - Baseline artifacts contract-complete in current release flow:
     - `ci.yml`
     - `publish-packages.yml`
     - `promote-prod.yml`
   - Additional `SPEC-0015` artifacts are active and mandatory in this release path:
     - `build-and-publish-image.yml`
     - `deploy-dev.yml`
     - `post-deploy-validate.yml`
     - `conformance-clients.yml`
5. Current release build contract:
   - buildspec: `buildspecs/buildspec-release.yml`
   - changed package publish set is resolved from signed release commit diff
     (`HEAD^..HEAD`) to prevent empty selective publish runs.
   - package uploads are pinned to CodeArtifact (`twine --repository codeartifact`).
   - default image build target:
     `apps/nova_file_api_service/Dockerfile`
   - CodeBuild inputs:
     `CODEARTIFACT_DOMAIN`, `CODEARTIFACT_REPOSITORY`,
     and ECR target (`ECR_REPOSITORY_URI` or `ECR_REPOSITORY_NAME`)
   - exported variables:
     `IMAGE_DIGEST`, `PUBLISHED_PACKAGES`,
     `RELEASE_MANIFEST_SHA256`, `CHANGED_UNITS`

## Documentation Map

- Requirements: `docs/architecture/requirements.md`
- ADR index: `docs/architecture/adr/index.md`
- SPEC index: `docs/architecture/spec/index.md`
- Target architecture ADR: `docs/architecture/adr/ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md`
- Route namespace ADR: `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- Target architecture SPEC: `docs/architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md`
- Route namespace SPEC: `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- Execution plan: `docs/plan/PLAN.md`
- Subplans: `docs/plan/subplans/`
- Trigger prompts: `docs/plan/triggers/`
- Release notes: `docs/plan/release/RELEASE-NOTES-2026-02-12.md`
- Hard-cutover checklist: `docs/plan/release/HARD-CUTOVER-CHECKLIST.md`
- Non-prod live validation runbook:
  `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- Version manifest:
  `docs/plan/release/RELEASE-VERSION-MANIFEST.md`
- Release policy:
  `docs/plan/release/RELEASE-POLICY.md`
- Release runbook:
  `docs/plan/release/RELEASE-RUNBOOK.md`
- Canonical runbooks: `docs/runbooks/README.md`
