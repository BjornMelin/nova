# nova runtime

![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-0.129%2B-009688?logo=fastapi&logoColor=white) ![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1-6BA539?logo=openapiinitiative&logoColor=white)

FastAPI control-plane runtime for direct-to-S3 uploads/downloads and async job
orchestration. The service returns presigned metadata and job state; it does not
proxy file bytes.

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
- `docs/architecture/spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md`
- `docs/architecture/spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md`
- `docs/architecture/spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md`
- `docs/architecture/spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md`

Engineering/operator deep references:

- `AGENTS.md`
- `docs/overview/NOVA-REPO-OVERVIEW.md`
- `docs/standards/README.md`
- `docs/runbooks/README.md`

Downstream/deploy-validation authority:

- `docs/architecture/adr/ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md`
- `docs/architecture/adr/ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md`
- `docs/architecture/adr/ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md`
- `docs/architecture/spec/SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md`
- `docs/architecture/spec/SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md`
- `docs/architecture/spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md`

Adjacent deployment-control-plane authority:

- `docs/architecture/adr/ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md`
- `docs/architecture/adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md`
- `docs/architecture/adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md`

Only canonical `/v1/*` routes and `/metrics/summary` are valid in active
contracts and operator runbooks.

## SDK Governance

Nova owns the client SDK contract surface, with Python as the current
release-grade public SDK, TypeScript retained as generated/private-distribution
contract surface, and R retained in-repo for parity scaffolding.

Current repository posture:

- committed Python SDK trees remain public, drift-gated client artifacts
- committed TypeScript SDK package trees remain private-distribution,
  drift-gated npm artifacts in the workspace and release pipeline
- committed TypeScript SDK packages `@nova/sdk-auth` and `@nova/sdk-file`
  are generated, OpenAPI-derived, transport-focused, and intentionally private
  in this wave
- the TypeScript `types` surfaces are curated from public operations and
  reachable public schemas only; raw whole-spec aliases are not part of the
  supported SDK contract
- TypeScript runtime validation is intentionally not bundled; consuming apps or
  BFF layers own their own validation boundary when needed
- R package scaffolding stays in-repo as the required foundation for parity and
  must not be deleted
- the TypeScript SDK packages install through the repo npm workspace in
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
- TypeScript SDK generation also strips internal-only schema aliases and
  requires explicit generated `contentType` selection when an operation
  exposes multiple request media types.
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
- In non-`same-origin` auth modes, `/v1/health/ready` includes the
  `auth_dependency` check.
- In `AUTH_MODE=jwt_local`, incomplete `OIDC_ISSUER`, `OIDC_AUDIENCE`, or
  `OIDC_JWKS_URL` configuration leaves the local verifier unavailable, which
  makes `auth_dependency` report not-ready.
- `POST /v1/internal/jobs/{job_id}/result` with `status=succeeded` normalizes
  `error` to `null`.
- Malformed worker queue messages are retried and drain to DLQ through SQS
  redrive policy; they are not acknowledged immediately.

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
cd <NOVA_REPO_ROOT>
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
runner is ephemeral. When CI or another ephemeral shell uses that command with
npm 10.x, AWS CLI v2.9.5 or newer is required.

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
  `JobsApiBaseUrl` and `JobsWorkerUpdateTokenSecretArn` inputs for the
  canonical `JOBS_*` runtime.
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
