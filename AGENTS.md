# AGENTS.md (nova runtime)

This repository is the canonical runtime monorepo for the Nova file-transfer
and auth API services.

## Runtime Topology

- `apps/nova_file_api_service/`: ASGI wrapper for file API runtime.
- `apps/nova_auth_api_service/`: ASGI wrapper for auth API runtime.
- `packages/nova_file_api/`: transfer + async jobs control-plane package.
- `packages/nova_auth_api/`: token verify/introspect service package.
- `packages/nova_dash_bridge/`: Dash/Flask/FastAPI bridge adapters.
- `packages/contracts/`: OpenAPI and shared contract artifacts.

Target public SDK posture:

- Nova must provide complete public SDKs for Python, TypeScript, and R.
- The repository currently ships the release-grade public Python SDK and keeps
  TypeScript as generated/private-distribution contract surface plus R
  scaffolding as the required path to full parity; do not delete that
  scaffolding.
- Internal-only operations remain excluded from client SDKs and belong to a
  separate internal/admin generation mode.

## Active Authority

Use these as the active authority set:

- `docs/PRD.md`
- `docs/architecture/requirements.md`
- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `docs/architecture/adr/ADR-0024-layered-architecture-authority-pack.md`
- `docs/architecture/adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md`
- `docs/architecture/adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md`
- `docs/architecture/adr/ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md`
- `docs/architecture/adr/ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md`
- `docs/architecture/adr/ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md`
- `docs/architecture/spec/SPEC-0000-http-api-contract.md`
- `docs/architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md`
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `docs/architecture/spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md`
- `docs/architecture/spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md`
- `docs/architecture/spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md`
- `docs/architecture/spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md`
- `docs/architecture/spec/SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md`
- `docs/architecture/spec/SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md`
- `docs/architecture/spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md`
- `docs/plan/PLAN.md`
- `docs/runbooks/README.md`

## Deep References

Start here for fresh-context repo work that needs more detail than this file:

- `README.md`
- `docs/overview/NOVA-REPO-OVERVIEW.md`
- `docs/standards/README.md`
- `docs/architecture/spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md`
- `docs/architecture/spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md`
- `docs/architecture/spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md`
- `docs/runbooks/README.md`

This repository currently uses a single root `AGENTS.md`. Do not add nested
`AGENTS.md` files unless a directory-local rule is both durable and materially
different from the repo root contract.

Adjacent deploy-governance authority (canonical, but not part of the active
runtime pack; these documents govern deployment, operational controls, and
CI/CD/IAM policy boundaries related to the product without defining the runtime
code or packaging surface):

- `docs/architecture/adr/ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md`
- `docs/architecture/adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md`
- `docs/architecture/adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md`
- `docs/architecture/spec/SPEC-0024-cloudformation-module-contract.md`
- `docs/architecture/spec/SPEC-0025-reusable-workflow-integration-contract.md`
- `docs/architecture/spec/SPEC-0026-ci-cd-iam-least-privilege-matrix.md`

Historical-only pointers:

- `PRD.md`
- `FINAL-PLAN.md`
- `docs/plan/HISTORY-INDEX.md`
- `docs/architecture/adr/superseded/**`
- `docs/architecture/spec/superseded/**`
- `docs/history/**`

## Canonical Route Rules

Runtime routes MUST be:

- `/v1/transfers/*`
- `/v1/jobs*`
- `/v1/internal/jobs/{job_id}/result` (internal worker only)
- `/v1/capabilities`
- `/v1/resources/plan`
- `/v1/releases/info`
- `/v1/health/live`
- `/v1/health/ready`
- `/metrics/summary`

Auth API routes MUST be:

- `/v1/token/verify`
- `/v1/token/introspect`
- `/v1/health/live`
- `/v1/health/ready`

Disallowed runtime route families:

- `/api/*`
- `/api/v1/*`
- `/healthz`
- `/readyz`

Do not add compatibility aliases or namespace shims.

Required route verification command:

```bash
source .venv/bin/activate && \
rg -n "/v1/transfers|/v1/jobs|/v1/internal/jobs|/v1/capabilities|/v1/resources/plan|/v1/releases/info|/v1/token/verify|/v1/token/introspect|/v1/health/live|/v1/health/ready|/metrics/summary" apps packages docs
```

## SDK/OpenAPI Generation Rules

- OpenAPI 3.1 artifacts are emitted from runtime application schemas
  (`/openapi.json`) and validated through runtime OpenAPI contract tests.
- Runtime OpenAPI `operationId` values are currently stable lowercase
  snake_case values derived from route and method literals.
- Runtime OpenAPI tags are currently implementation-owned and include router
  tags such as `transfers`, `ops`, and `v1` for file API surfaces.
- Custom request-body `$ref` entries added through `openapi_extra` MUST resolve
  to named component schemas in the emitted OpenAPI document.
- Generated-client compatibility is validated through
  `packages/nova_file_api/tests/test_generated_client_smoke.py`.
- Generated TypeScript SDKs must expose curated operation/schema helpers only;
  raw whole-spec aliases and internal worker-only models are not public
  contract.
- Generated TypeScript SDK packages are `@nova/sdk-auth`, `@nova/sdk-file`, and
  the shared runtime/helper package `@nova/sdk-fetch`; they remain
  private-distribution artifacts in this wave.
- Generated TypeScript SDKs must honor the request media types declared in
  OpenAPI.
  Multi-media request bodies use explicit generated `contentType` selection.
- Generated TypeScript SDK packages are validation-free: do not add `zod`,
  validator packages, validator subpaths, or runtime request/response
  validation helpers to these packages. App/BFF validation belongs to
  consumers.
- Generated TypeScript SDK packages must not expose package-root `"."` exports.
- TypeScript module policy is strict: do not create or retain `index.ts` barrel
  files, do not use `export ... from` re-export barrels, and always import from
  explicit module subpaths (for example `@nova/sdk-fetch/url`,
  `@nova/sdk-fetch/client`, `@nova/sdk-auth/client`,
  `@nova/sdk-auth/operations`, `@nova/sdk-file/client`, and
  `@nova/sdk-file/types`).
- Internal/admin operations marked with `x-nova-sdk-visibility: internal` must
  remain excluded from generated TypeScript SDK output.
- Treat generated TypeScript SDK outputs as generator-owned. Prefer changing
  runtime OpenAPI producers, committed OpenAPI artifacts, or
  `scripts/release/generate_clients.py` before editing generated SDK output by
  hand.
- Do not reintroduce stale authority paths, root exports, runtime validation
  libraries, or duplicated transport logic in the generated TypeScript SDKs.

## npm / CodeArtifact Local Rule

- Keep npm registry config repo-local. Use the committed repo-root `.npmrc`
  for checked-in defaults, and use the generated `.npmrc.codeartifact` for
  CodeArtifact auth; never put Nova CodeArtifact npm settings in global
  `~/.npmrc`.
- For local npm access, run from the repository root:
  `eval "$(npm run -s codeartifact:npm:env)"`
- `scripts/release/codeartifact_npm.py` writes `.npmrc.codeartifact` and the
  helper exports `NPM_CONFIG_USERCONFIG` to that path.
- If you switch AWS accounts or CodeArtifact targets, set `AWS_REGION`,
  `CODEARTIFACT_DOMAIN`, and/or `CODEARTIFACT_STAGING_REPOSITORY` before
  running the helper.
- Do not run `aws codeartifact login --tool npm` on a developer workstation.
  It rewrites global npm config. CI may use it on ephemeral runners. npm 10.x
  requires AWS CLI v2.9.5 or newer for this command.

## Runtime Invariants

- `POST /v1/jobs` queue publish failures MUST return `503` with
  `error.code = "queue_unavailable"`.
- Mutation entrypoints running with distributed idempotency MAY return `503`
  with `error.code = "idempotency_unavailable"` when the shared claim store
  cannot guarantee correctness.
- Failed enqueue responses MUST NOT be idempotency replay cached.
- `IDEMPOTENCY_ENABLED=true` with `IDEMPOTENCY_MODE=shared_required` requires
  `CACHE_REDIS_URL`.
- Multi-instance production posture for idempotent mutation entrypoints MUST use
  `IDEMPOTENCY_MODE=shared_required`; do not treat `local_only` as a production
  default.
- `/v1/health/ready` must evaluate only traffic-critical dependencies.
- Missing/blank `FILE_TRANSFER_BUCKET` MUST fail readiness.
- `AUTH_MODE=jwt_local` with incomplete `OIDC_ISSUER`, `OIDC_AUDIENCE`, or
  `OIDC_JWKS_URL` MUST fail the `auth_dependency` readiness check on
  `/v1/health/ready`.
- `POST /v1/internal/jobs/{job_id}/result` with `status=succeeded` MUST clear
  `error` to `null`.
- Do not log presigned URLs, JWTs, or signed query values.
- Do not run synchronous JWT verification directly on async event-loop paths;
  use a threadpool boundary.
- `JOBS_QUEUE_BACKEND=sqs` with `JOBS_ENABLED=true` requires
  `JOBS_SQS_QUEUE_URL`.
- `JOBS_REPOSITORY_BACKEND=dynamodb` requires `JOBS_DYNAMODB_TABLE`.
- DynamoDB-backed job listing requires the jobs table GSI
  `scope_id-created_at-index`; the runtime does not fall back to `Scan` for
  scoped listing.
- `JOBS_RUNTIME_MODE=worker` requires `JOBS_ENABLED=true`,
  `JOBS_QUEUE_BACKEND=sqs`, `JOBS_SQS_QUEUE_URL`, `JOBS_API_BASE_URL`, and
  `JOBS_WORKER_UPDATE_TOKEN`.
- Malformed worker queue messages MUST remain unacked so SQS retry/DLQ policy
  handles poison messages; the worker must not delete them immediately.
- `ACTIVITY_STORE_BACKEND=dynamodb` requires `ACTIVITY_ROLLUPS_TABLE`.

## Required Quality Gates

Always run from repository root with `.venv` active.

Always-run repo gates:

```bash
source .venv/bin/activate && uv lock --check
source .venv/bin/activate && uv run ruff check .
source .venv/bin/activate && uv run ruff check . --select I
source .venv/bin/activate && uv run ruff format . --check
source .venv/bin/activate && uv run mypy
source .venv/bin/activate && uv run pytest -q
source .venv/bin/activate && uv run pytest -q \
  packages/nova_file_api/tests/test_generated_client_smoke.py
source .venv/bin/activate && uv run python scripts/contracts/export_openapi.py --check
source .venv/bin/activate && uv run python scripts/release/generate_clients.py --check
source .venv/bin/activate && uv run python scripts/release/generate_python_clients.py --check
source .venv/bin/activate && \
for p in packages/nova_file_api packages/nova_auth_api \
  packages/nova_dash_bridge apps/nova_file_api_service \
  apps/nova_auth_api_service; do uv build "$p"; done
```

Additional required gates when touching OpenAPI, generated TypeScript SDKs, npm
packaging, release automation, or SDK docs/contracts:

```bash
source .venv/bin/activate && uv run python scripts/conformance/check_typescript_module_policy.py
npm run -w @nova/sdk-fetch build
npm run -w @nova/sdk-fetch typecheck
npm run -w @nova/sdk-auth typecheck
npm run -w @nova/sdk-file typecheck
npm run -w @nova/contracts-ts-conformance typecheck
npm run -w @nova/contracts-ts-conformance verify
source .venv/bin/activate && uv run pytest -q scripts/release/tests/test_typescript_sdk_contracts.py
```

## Documentation Update Rules

Any behavioral or contract change MUST update all affected docs in the same PR:

- `README.md`
- `docs/PRD.md`
- `docs/architecture/requirements.md`
- affected `docs/architecture/adr/*.md`
- affected `docs/architecture/spec/*.md`
- affected `docs/standards/*.md`
- `docs/plan/PLAN.md`
- affected `docs/contracts/*.json`
- affected `docs/clients/*.md` and `docs/clients/**/*.yml` for downstream integration contracts
- affected `docs/plan/release/*.md`
- `docs/runbooks/README.md` when runbook authority changes
- `docs/architecture/adr/superseded/**` and
  `docs/architecture/spec/superseded/**` when active authority is superseded
- `docs/history/**` when archival paths/evidence pointers change
- `PRD.md` and `FINAL-PLAN.md` only when archive pointers change
- `AGENTS.md` when the durable operator contract changes

## Cross-Repo Check (dash-pca)

Path: `~/repos/work/pca-analysis-dash/dash-pca`

```bash
rg -n "/v1/transfers|/v1/jobs|nova_dash_bridge|nova_file_api" \
  ~/repos/work/pca-analysis-dash/dash-pca
```

## Historical Retirement Check

```bash
rg -n "container-craft" README.md docs/architecture docs/plan docs/runbooks \
  | rg -v "docs/history|docs/architecture/adr/superseded|docs/architecture/spec/superseded|historical|archive|retired|ADR-0001|SPEC-0013|SPEC-0014|requirements.md|RELEASE-VERSION-MANIFEST"
```
