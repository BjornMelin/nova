# nova runtime

![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-0.129%2B-009688?logo=fastapi&logoColor=white) ![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1-6BA539?logo=openapiinitiative&logoColor=white)

FastAPI control-plane runtime for direct-to-S3 uploads/downloads and async job
orchestration. The service returns presigned metadata and job state; it does not
proxy file bytes.

The canonical async worker lane executes `transfer.process` jobs by
server-side copying a scoped upload object into the export prefix and returning
`export_key` plus `download_filename`. For async worker retries, the same
`job_id` reuses the same export key so SQS replay does not mint duplicate
export objects.

## Canonical Contract

Active route authority is hard-cut canonical `/v1/*` plus `/metrics/summary`:

- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `docs/architecture/spec/SPEC-0000-http-api-contract.md`
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`

Topology and release-delivery authority:

- `docs/architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md`
- `docs/architecture/adr/ADR-0024-layered-architecture-authority-pack.md`
- `docs/architecture/adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md`
- `docs/architecture/adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md`

Adjacent deployment-control-plane authority:

- `docs/architecture/adr/ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md`
- `docs/architecture/adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md`
- `docs/architecture/adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md`
- `docs/architecture/spec/SPEC-0024-cloudformation-module-contract.md`
- `docs/architecture/spec/SPEC-0025-reusable-workflow-integration-contract.md`
- `docs/architecture/spec/SPEC-0026-ci-cd-iam-least-privilege-matrix.md`

Only canonical `/v1/*` routes and `/metrics/summary` are valid in active
contracts and operator runbooks.

## SDK Governance

Python SDKs are the only release-grade public client surface in this wave.

Current repository posture:

- committed Python SDK trees remain the public, drift-gated client artifacts
  used today
- TypeScript and R package scaffolding stays in-repo as internal/generated
  foundation work and must not be deleted ahead of a later promotion wave
- the TypeScript foundation packages install through the repo npm workspace in
  source/CI mode and publish as private CodeArtifact npm packages with concrete
  semver dependencies during staged release promotion
- internal-only operations such as
  `/v1/internal/jobs/{job_id}/result` are intentionally excluded from client
  SDK generation

SDK-facing OpenAPI rules are hard requirements:

- `operationId` values are stable lowercase snake_case names, not FastAPI
  path/method-derived identifiers.
- Tags are semantic SDK groupings only: `transfers`, `jobs`, `platform`,
  `ops`, `token`, and `health`.
- Committed SDK artifacts regenerate from
  `packages/contracts/openapi/*.openapi.json` via
  `scripts/release/generate_clients.py` and
  `scripts/release/generate_python_clients.py`.
- Public SDK generation strips internal-only operations marked with
  `x-nova-sdk-visibility: internal`.
- Published runtime Python distributions `nova_file_api` and `nova_auth_api`
  include `py.typed` markers for installed-package type checking.

## Runtime Capability Families

- Transfer orchestration: `/v1/transfers/*`
- Async job control plane: `/v1/jobs*`
- Internal worker update path: `/v1/internal/jobs/{job_id}/result`
- Capability/release discovery: `/v1/capabilities`, `/v1/resources/plan`,
  `/v1/releases/info`
- Operational health: `/v1/health/live`, `/v1/health/ready`
- Metrics summary: `/metrics/summary`

For exact endpoint and payload contract details, use:

- `docs/architecture/spec/SPEC-0000-http-api-contract.md`
- OpenAPI schema from runtime code

## Runtime Invariants

- `POST /v1/jobs` publish failures return `503` with
  `error.code = "queue_unavailable"`.
- Strict shared-idempotency claim-store outages return `503` with
  `error.code = "idempotency_unavailable"` for idempotent mutation entrypoints.
- `IDEMPOTENCY_MODE=shared_required` requires `CACHE_REDIS_URL`; production
  deployments must not run idempotent mutation endpoints in `local_only` mode.
- Failed enqueue responses are not idempotency replay cached.
- `/v1/health/ready` is dependency-scoped and fails on blank
  `FILE_TRANSFER_BUCKET`.
- `/v1/health/ready` also fails on shared-cache health when shared-cache-backed
  idempotency is the configured traffic-critical mode.
- `AUTH_MODE=jwt_local` with incomplete `OIDC_ISSUER`, `OIDC_AUDIENCE`, or
  `OIDC_JWKS_URL` configuration fails the `auth_dependency` readiness check.
- `POST /v1/internal/jobs/{job_id}/result` with `status=succeeded` normalizes
  `error` to `null`.
- SQS-backed worker messages are work requests only:
  `job_id`, `job_type`, `scope_id`, `payload`, and `created_at`.
- `transfer.process` is the canonical async job type; successful worker
  completion returns `export_key` and `download_filename`.
- Malformed worker queue messages are retried and drain to DLQ through SQS
  redrive policy; they are not acknowledged immediately.
- Worker result callbacks must be durably accepted before a message is deleted;
  transient callback rejection leaves the source message on the queue for
  retry/DLQ handling.

## Local Development

```bash
source .venv/bin/activate && uv lock --check
source .venv/bin/activate && uv run ruff check .
source .venv/bin/activate && uv run ruff check . --select I
source .venv/bin/activate && uv run ruff format . --check
source .venv/bin/activate && uv run mypy
source .venv/bin/activate && uv run pytest -q
```

Run generated-client contract smoke:

```bash
source .venv/bin/activate && \
uv run pytest -q packages/nova_file_api/tests/test_generated_client_smoke.py
```

Package/app metadata isolation builds:

```bash
source .venv/bin/activate && \
for p in packages/nova_file_api packages/nova_auth_api \
  packages/nova_dash_bridge apps/nova_file_api_service \
  apps/nova_auth_api_service; do uv build "$p"; done
```

TypeScript/CodeArtifact local auth stays repo-scoped:

```bash
cd /home/bjorn/repos/work/infra-stack/nova
eval "$(npm run -s codeartifact:npm:env)"
npm install --no-package-lock
```

The committed `.npmrc`
leaves the default registry on `registry.npmjs.org`. The helper above writes a
repo-local `.npmrc.codeartifact`
from the current AWS credentials and points npm at it through
`NPM_CONFIG_USERCONFIG`, so other repos stay untouched. To target a different
AWS account/domain/repository, set `AWS_REGION`, `CODEARTIFACT_DOMAIN`, and/or
`CODEARTIFACT_STAGING_REPOSITORY` before running the helper. Do not use
`aws codeartifact login --tool npm` for local developer shells because it
rewrites global `~/.npmrc`; that command remains acceptable in CI where the
runner is ephemeral.

## Release and Operations

Canonical runbook entrypoint:

- `docs/runbooks/README.md`

Release sequencing contract:

- Runtime-first deploy: provision `infra/runtime/**` stacks for `dev` and
  `prod` before CI/CD stack rollout.
- Foundation-first control plane: `nova-foundation` is deployed before IAM,
  CodeBuild, and CodePipeline stacks.
- Runtime deployment target is ECS/Fargate behind ALB with ECS-native
  blue/green deployment strategy, CloudWatch deployment alarms, and WAF on the
  public ALB path.
- Worker deployment contract uses the packaged `nova-file-worker` command plus
  `JobsApiBaseUrl` and mandatory `JobsWorkerUpdateTokenSecretArn` inputs for
  the canonical `JOBS_*` runtime, including scale-from-zero worker services.
- Worker autoscaling uses explicit queue-depth step scaling
  (bootstrap/backlog/surge plus empty-queue scale-in) and keeps
  `ApproximateAgeOfOldestMessage` as an operator alarm.
- Reusable GitHub workflows are published as versioned automation APIs:
  `@v1` is the compatibility channel, while production consumers pin immutable
  `@v1.x.y` tags or full commit SHAs.
- Composite actions under `.github/actions/**` are internal implementation
  details behind the reusable workflow API surface.
- Base URL authority: deploy validation URLs are sourced from
  `/nova/{env}/{service}/base-url` via
  `infra/nova/deploy/service-base-url-ssm.yml`.
- Release manifest hashing must describe the actual
  `docs/plan/release/RELEASE-VERSION-MANIFEST.md` content promoted across lanes.

Key active release docs:

- `docs/plan/release/RELEASE-RUNBOOK.md`
- `docs/plan/release/RELEASE-POLICY.md`
- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- `docs/plan/release/AUTH0-A0DEPLOY-RUNBOOK.md`
- `docs/plan/release/deploy-runtime-cloudformation-environments-guide.md`
- `docs/plan/release/HARD-CUTOVER-CHECKLIST.md`
- `docs/plan/release/RELEASE-VERSION-MANIFEST.md`

## Documentation Authority Map

Active docs:

- Product requirements: `docs/PRD.md`
- Requirements: `docs/architecture/requirements.md`
- ADR index: `docs/architecture/adr/index.md`
- SPEC index: `docs/architecture/spec/index.md`
- Plan index: `docs/plan/PLAN.md`

Historical docs:

- History index: `docs/plan/HISTORY-INDEX.md`
- Archive root: `docs/history/README.md`
- Archived release notes: `docs/history/2026-02-cutover/release/RELEASE-NOTES-2026-02-12.md`
