# AGENTS.md (nova runtime)

Nova is the canonical runtime monorepo for the file-transfer API (including
**in-process bearer JWT** in the target architecture), retired dedicated auth
service packages, and adapter surfaces.

## Start Here

Read these in order for fresh-context work:

1. `docs/README.md`
2. `docs/architecture/README.md`
3. `README.md`
4. `docs/standards/README.md`
5. `docs/runbooks/README.md` when the task affects release or operations

This repository intentionally uses a single root `AGENTS.md`. Do not add nested
`AGENTS.md` files unless a directory-local rule is durable and materially
different.

## Runtime Topology

- `packages/nova_file_api/`: transfer, jobs, readiness, metrics, ASGI
  entrypoint, worker orchestration, and bearer JWT verification in the target
  architecture (`ADR-0033`, `SPEC-0027`).
- `packages/nova_dash_bridge/`: Dash/Flask/FastAPI integration adapters over
  the canonical `nova_file_api.public` surface.
- `packages/nova_runtime_support/`: shared runtime support helpers, including
  outer-ASGI request context, canonical FastAPI exception registration, log
  redaction, and shared auth helpers.
- `packages/contracts/`: OpenAPI artifacts and contract inputs.

Workspace packaging rules:

- Runtime packages must declare explicit intra-workspace runtime dependencies in
  their own `pyproject.toml` files.
- Do not rely on root workspace sync/install shape as an implicit production
  contract.

SDK posture:

- Nova must provide complete public SDKs for Python, TypeScript, and R.
- Python is the release-grade public SDK surface.
- TypeScript is release-grade within Nova's existing CodeArtifact staged/prod
  system while remaining generator-owned and subpath-only, using
  `openapi-typescript` + `openapi-fetch` per `ADR-0038` / `SPEC-0029`.
- R packages are first-class internal release artifacts with real package
  trees, logical format `r`, CodeArtifact generic transport, and signed tarball
  evidence.
- Internal-only operations remain excluded from public SDK generation.
- Public TypeScript SDK packages must not expose package-root `"."` exports.
- Operations marked with `x-nova-sdk-visibility: internal` remain excluded.
- Generated TypeScript SDKs must honor declared request media types and use
  explicit generated `contentType` selection for multi-media bodies.
- Do not add `zod`, validator packages, validator subpaths, or runtime
  request/response validation helpers to generated TypeScript SDKs.
- Do not create or retain `index.ts` barrels or `export … from`
  re-export barrels in generated TypeScript SDK packages; use explicit module
  subpaths.
- Prefer fixing generator-owned SDK output through runtime OpenAPI producers,
  committed OpenAPI artifacts, or `scripts/release/generate_clients.py`.

## Authority Entry Points

- Canonical route chain:
  - `docs/architecture/requirements.md`
  - `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
  - `docs/architecture/spec/SPEC-0000-http-api-contract.md`
  - `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
  - `docs/architecture/spec/SPEC-0027-public-http-contract-revision-and-bearer-auth.md`
- Green-field program:
  - `docs/plan/greenfield-simplification-program.md`
  - `docs/plan/greenfield-authority-map.md`
  - `docs/architecture/adr/ADR-0033-single-runtime-auth-authority.md`
    through `ADR-0041-shared-pure-asgi-middleware-and-errors.md`
- Product and topology context:
  - `docs/PRD.md`
  - `docs/architecture/adr/ADR-0024-layered-architecture-authority-pack.md`
  - `docs/architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md`
- Runtime topology and safety pack:
  - `docs/architecture/adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md`
  - `docs/architecture/adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md`
  - `docs/architecture/spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md`
  - `docs/architecture/spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md`
  - `docs/architecture/spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md`
  - `docs/architecture/spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md`
- Downstream validation pack:
  - `docs/architecture/adr/ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md`
  - `docs/architecture/adr/ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md`
  - `docs/architecture/adr/ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md`
  - `docs/architecture/spec/SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md`
  - `docs/architecture/spec/SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md`
  - `docs/architecture/spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md`
- Adjacent deploy-governance pack:
  - `docs/architecture/spec/SPEC-0024-cloudformation-module-contract.md`
  - `docs/architecture/spec/SPEC-0025-reusable-workflow-integration-contract.md`
  - `docs/architecture/spec/SPEC-0026-ci-cd-iam-least-privilege-matrix.md`
- SDK and release-artifact governance pack:
  - `docs/architecture/adr/ADR-0038-sdk-architecture-by-language.md`
  - `docs/architecture/spec/SPEC-0029-sdk-architecture-and-artifact-contract.md`
  - `docs/architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`

## Docs Sync Rules

- Keep `AGENTS.md`, `README.md`, `docs/README.md`, and the relevant active
  authority docs aligned in the same change set when runtime contracts or
  operator workflows change.
- Bridge/browser auth changes must keep downstream guidance aligned on the
  bearer-only `nova_dash_bridge -> nova_file_api.public` seam and canonical
  `/v1/transfers` + `/v1/jobs` routes.
- Runtime deploy docs must describe `AUTH_MODE=jwt_local` OIDC completeness as
  a Nova readiness/runtime contract. Do not move that enforcement back into
  CloudFormation template validation.
- FastAPI transport changes must keep `packages/nova_runtime_support` as the
  single owner of outer-ASGI request context and shared exception registration.
  `nova_dash_bridge.create_fastapi_router()` stays route-only composition;
  standalone hosts must install the shared runtime stack explicitly.
- Adapter-surface changes must keep `nova_file_api.public` async-first.
  FastAPI hosts call that async surface directly; sync wrappers are explicit
  secondary adapters for true sync hosts such as Flask/Dash only.
- Downstream consumer docs must not describe `session_id`, `X-Session-Id`, or
  `X-Scope-Id` as valid public auth inputs.

## Canonical Guardrails

- Public runtime routes are canonical `/v1/*` plus `/metrics/summary`.
- Public callers authenticate with **bearer JWT** verified in `nova_file_api`;
  there is **no** separate `/v1/token/verify` or `/v1/token/introspect` surface
  in the target architecture (`ADR-0033`, `ADR-0034`, `SPEC-0027`).
- Operational health for the public service remains at `/v1/health/live` and
  `/v1/health/ready`.
- Do not add compatibility aliases or namespace shims such as `/api/*`,
  `/api/v1/*`, `/healthz`, or `/readyz`.
- `nova_dash_bridge` is an adapter package. It may forward context and call
  canonical Nova contracts through `nova_file_api.public`, but it must not
  redefine route, auth, or storage authority.
- `nova_file_api.public` is the canonical in-process transfer contract. Its
  transfer factory/config surface is plain-data and async-first; do not add
  public `BaseSettings` synthesis or restore bridge-local sync-over-async
  threadpool hops for FastAPI.
- FastAPI applications that need canonical Nova request-id propagation and
  error-envelope behavior must install the shared outer-ASGI request-context
  wrapper and shared exception registration from `nova_runtime_support`.
- OpenAPI 3.1 emitted from runtime code is the contract source for docs and SDK
  generation.
- OpenAPI `operationId` values must remain stable snake_case names, and tags
  must remain semantic groupings used by the contract tests.
- Custom request-body `$ref` values injected through `openapi_extra` must
  resolve to named component schemas in emitted OpenAPI.
- Generated-client compatibility is enforced by
  `packages/nova_file_api/tests/test_generated_client_smoke.py`.
- Never log presigned URLs, JWTs, or signed query values.
- Keep `.agents/AUDIT_DELIVERABLES/*` updated locally for dev tracking, but
  leave it ignored and never commit it in PRs.

Quick route preflight:

```bash
source .venv/bin/activate && \
rg -n "/v1/transfers|/v1/jobs|/v1/capabilities|/v1/resources/plan|/v1/releases/info|/v1/health/live|/v1/health/ready|/metrics/summary" packages docs
```

## Runtime Invariants

- `POST /v1/jobs` queue publish failures must return `503` with
  `error.code = "queue_unavailable"`.
- Mutation entrypoints running with idempotency require a shared Redis claim
  store. Shared-store failures must return `503` with
  `error.code = "idempotency_unavailable"` instead of falling back to local
  claim handling.
- Failed enqueue responses must not be idempotency replay cached.
- `IDEMPOTENCY_ENABLED` and `IDEMPOTENCY_TTL_SECONDS` are the current
  idempotency settings surface; do not add or document `IDEMPOTENCY_MODE`.
- `IDEMPOTENCY_ENABLED=true` requires `CACHE_REDIS_URL`.
- `/v1/health/ready` returns `503` when a traffic-critical readiness check is
  false.
- Missing or blank `FILE_TRANSFER_BUCKET` must fail readiness.
- `AUTH_MODE=jwt_local` with incomplete `OIDC_ISSUER`, `OIDC_AUDIENCE`, or
  `OIDC_JWKS_URL` must fail the `auth_dependency` readiness check.
- Shared cache only gates readiness when idempotency is enabled; activity-store
  health remains visible but is not readiness-fatal in the current contract.
- Prefer **async-native** JWT verification in `nova_file_api` when implemented
  (`ADR-0033`, `ADR-0037`); any **remaining** synchronous verification on async
  paths must use a threadpool boundary (`ADR-0026`, `SPEC-0019`).
- Worker terminal updates that set `status=succeeded` must clear `error` to
  `null` on the **direct persistence** path (`SPEC-0028`, `ADR-0035`).
- `JOBS_QUEUE_BACKEND=sqs` with `JOBS_ENABLED=true` requires
  `JOBS_SQS_QUEUE_URL`.
- `JOBS_REPOSITORY_BACKEND=dynamodb` requires `JOBS_DYNAMODB_TABLE`.
- DynamoDB-backed job listing requires the
  `scope_id-created_at-index` GSI; do not fall back to `Scan`.
- `JOBS_RUNTIME_MODE=worker` requires `JOBS_ENABLED=true`,
  `JOBS_QUEUE_BACKEND=sqs`, `JOBS_SQS_QUEUE_URL`,
  `JOBS_REPOSITORY_BACKEND=dynamodb`, `JOBS_DYNAMODB_TABLE`,
  `ACTIVITY_STORE_BACKEND=dynamodb`, and `ACTIVITY_ROLLUPS_TABLE`.
  HTTP callback settings (`JOBS_API_BASE_URL`, `JOBS_WORKER_UPDATE_TOKEN`)
  are **not** part of the target architecture once direct persistence is
  implemented (`SPEC-0028`).
- Malformed worker queue messages must remain unacked so SQS retry/DLQ policy
  handles poison messages.
- `ACTIVITY_STORE_BACKEND=dynamodb` requires `ACTIVITY_ROLLUPS_TABLE`.
- The runtime ECS service stack owns its repo-managed task role and cache
  secret injection. Do not pass `TASK_ROLE_ARN`,
  `TASK_EXECUTION_SECRET_ARNS`, or `TASK_EXECUTION_SSM_PARAMETER_ARNS` to
  `scripts/release/deploy-runtime-cloudformation-environment.sh`.

## Task Router

Use the baseline gates for most code changes, then expand based on what you
touched.

### Runtime code under runtime packages

Run:

```bash
npm ci
source .venv/bin/activate && uv lock --check
source .venv/bin/activate && uv run ruff check .
source .venv/bin/activate && uv run ruff check . --select I
source .venv/bin/activate && uv run ruff format . --check
source .venv/bin/activate && uv run ty check --force-exclude --error-on-warning packages scripts
source .venv/bin/activate && uv run mypy
source .venv/bin/activate && uv run pytest -q
source .venv/bin/activate && uv run pytest -q \
  packages/nova_file_api/tests/test_generated_client_smoke.py
source .venv/bin/activate && uv run python scripts/contracts/export_openapi.py --check
source .venv/bin/activate && uv run python scripts/release/generate_runtime_config_contract.py --check
source .venv/bin/activate && uv run python scripts/release/generate_clients.py --check
source .venv/bin/activate && uv run python scripts/release/generate_python_clients.py --check
source .venv/bin/activate && \
for p in packages/nova_file_api packages/nova_dash_bridge; do uv build "$p"; done
```

Notes:

- `ty` is the canonical Python type gate for the full repo typing surface.
- `mypy` remains a required compatibility backstop on its narrower configured
  scope.
- `scripts/release/generate_clients.py --check` requires the repo-installed
  root npm toolchain; run `npm ci` before generated TypeScript SDK gates so the
  local `openapi-typescript` CLI is available without ad hoc network fetches.
- `pyproject.toml` pins the supported `uv` CLI via
  `[tool.uv].required-version`; keep local tooling, CI, and docs aligned when
  bumping that version.
- Pytest runs in `--import-mode=importlib` against editable workspace installs.
  Do not add repo-level `pythonpath` overrides back unless a newly verified
  import failure requires them.
- Runtime config deploy/docs/tests must treat
  `packages/nova_file_api/src/nova_file_api/config.py` plus
  `scripts/release/runtime_config_contract.py` as the source-of-truth pair and
  keep `docs/release/runtime-config-contract.generated.md` fresh via
  `scripts/release/generate_runtime_config_contract.py`.
- CI also enforces a stronger canonical-route policy guard in
  `.github/workflows/ci.yml`. Use the quick route preflight above before
  broader edits.
- If you touch `packages/nova_runtime_support`, also run:
  `source .venv/bin/activate && uv build packages/nova_runtime_support`

### Pre-commit hooks

Install repo hooks with:

```bash
source .venv/bin/activate && uv sync --locked
source .venv/bin/activate && uv run pre-commit install --install-hooks \
  --hook-type pre-commit --hook-type pre-push
```

If `uv` is not on `PATH`, install it first, then rerun
`scripts/dev/install_hooks.sh`.

Manual pre-commit hook entrypoints mirror the task router:

- `uv run pre-commit run typing-gates --hook-stage manual -a`
- `uv run pre-commit run quality-gates --hook-stage manual -a`
- `uv run pre-commit run sdk-conformance --hook-stage manual -a`
- `uv run pre-commit run infra-contracts --hook-stage manual -a`
- `uv run pre-commit run docker-release-images --hook-stage manual -a`

### OpenAPI, generated SDKs, npm packaging, or SDK docs/contracts

Also run the conformance/client checks mirrored by
`.github/workflows/ci.yml`:

```bash
npm ci
source .venv/bin/activate && uv run python scripts/conformance/check_typescript_module_policy.py
npm run -w @nova/sdk-fetch build
npm run -w @nova/sdk-fetch typecheck
npm run -w @nova/sdk-file typecheck
npm run -w @nova/sdk-file build
npm run -w @nova/contracts-ts-conformance typecheck
npm run -w @nova/contracts-ts-conformance verify
source .venv/bin/activate && uv run pytest -q scripts/release/tests/test_typescript_sdk_contracts.py
```

### R package artifacts, release packaging, or R SDK docs/contracts

Also run the shared R conformance entrypoint:

```bash
source .venv/bin/activate && bash scripts/checks/run_sdk_conformance.sh
```

Notes:

- `scripts/checks/run_sdk_conformance.sh` wraps
  `scripts/checks/verify_r_cmd_check.sh`.
- The helper parses `00check.log` and fails the lane when `R CMD check`
  reports warnings.

### Infra, workflows, or docs governance

Use the docs/infra contract checks mirrored by
`.github/workflows/cfn-contract-validate.yml`:

```bash
source .venv/bin/activate && uv run --with cfn-lint==1.46.0 cfn-lint infra/nova/*.yml infra/nova/deploy/*.yml infra/runtime/**/*.yml
source .venv/bin/activate && uv run --with pytest pytest -q \
  tests/infra/test_absorbed_infra_contracts.py \
  tests/infra/test_workflow_productization_contracts.py \
  tests/infra/test_workflow_contract_docs.py \
  tests/infra/test_docs_authority_contracts.py
```

### Service Dockerfiles or release-image build flow

Use this when touching `apps/nova_file_api_service/Dockerfile`,
`buildspecs/buildspec-release.yml`, or release-image documentation:

```bash
docker buildx version
DOCKER_BUILDKIT=1 docker buildx build --load \
  -f apps/nova_file_api_service/Dockerfile \
  -t nova-file-api:test .
source .venv/bin/activate && uv run pytest -q \
  packages/nova_file_api/tests/test_runtime_security_reliability_gates.py \
  tests/infra/test_workflow_productization_contracts.py \
  tests/infra/test_workflow_contract_docs.py \
  tests/infra/test_docs_authority_contracts.py
```

Notes:

- Release-owned service Dockerfiles stay under `apps/*`; do not move them into
  workspace package paths.
- Local service-image verification and release builds now require Docker
  BuildKit plus `buildx`.
- If local Docker hits plugin-path or credential-helper failures, use
  `docs/runbooks/provisioning/docker-buildx-credential-helper-setup.md`.

### Downstream route or bridge contract changes

Spot check the Dash downstream consumer:

```bash
export DASH_PCA_REPO="${DASH_PCA_REPO:?set DASH_PCA_REPO to your dash-pca checkout}"
rg -n "/v1/transfers|/v1/jobs|nova_dash_bridge|nova_file_api" \
  "${DASH_PCA_REPO}"
```

## Documentation Rules

If behavior, contracts, workflows, or durable repo instructions change, update
the relevant docs in the same PR.

Minimum router set:

- `AGENTS.md`
- `README.md`
- `docs/README.md`
- `docs/architecture/README.md`
- `docs/standards/README.md`
- `docs/runbooks/README.md`
- `docs/plan/PLAN.md`

Then update affected authority docs:

- `docs/PRD.md`
- `docs/architecture/requirements.md`
- affected ADRs and SPECs
- affected `docs/contracts/**`, `docs/clients/**`, and release docs
- history/superseded docs only when archive location or authority status changes

Use `docs/standards/repository-engineering-standards.md` for the full gate
matrix and deeper documentation synchronization rules.

Historical retirement spot check:

```bash
rg -n "container-craft" README.md docs/architecture docs/plan docs/runbooks \
  | rg -v "docs/history|docs/architecture/adr/superseded|docs/architecture/spec/superseded|historical|archive|retired|ADR-0001|SPEC-0013|SPEC-0014|requirements.md|RELEASE-VERSION-MANIFEST"
```

## Local npm / CodeArtifact Rule

Keep npm registry config repo-local.

- Use the committed repo-root `.npmrc` for defaults.
- Use the generated `.npmrc.codeartifact` for CodeArtifact auth.
- Run `eval "$(npm run -s codeartifact:npm:env)"` from repo root.
- `scripts/release/codeartifact_npm.py` writes `.npmrc.codeartifact` and the
  helper exports `NPM_CONFIG_USERCONFIG` plus `NPM_REGISTRY_URL`.
- CI and release workflows must use the same explicit `NPM_CONFIG_USERCONFIG`
  pattern (or an equivalent temp-file variant); do not rely on global npm
  config mutation.
- If you switch AWS accounts or CodeArtifact targets, set `AWS_REGION`,
  `CODEARTIFACT_DOMAIN`, and/or `CODEARTIFACT_STAGING_REPOSITORY` before
  running the helper.
- Do not use `aws codeartifact login --tool npm` in Nova. It rewrites global
  npm config and is not part of the canonical release path.

## Deep References

- `docs/overview/NOVA-REPO-OVERVIEW.md`
- `docs/plan/PLAN.md`
- `docs/architecture/adr/index.md`
- `docs/architecture/spec/index.md`
- `docs/history/README.md` when tracing retired or superseded program archives
