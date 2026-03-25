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
- Python SDK generation is pinned to `openapi-python-client==0.28.3` and uses
  committed generator config/templates under
  `scripts/release/openapi_python_client/`.
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
- Prefer fixing generator-owned Python SDK output through OpenAPI producers,
  committed OpenAPI artifacts, generator config, or the minimal committed
  templates. Do not reintroduce a large post-generation patch layer.

## Authority Entry Points

Use these routers instead of restating partial authority packs:

- `docs/README.md` for repo-wide documentation routing
- `docs/architecture/README.md` for the canonical route chain, active
  architecture authority packs, and deploy-governance pack membership
- `docs/standards/README.md` and
  `docs/standards/repository-engineering-standards.md` for docs-sync policy,
  gate ownership, and deeper operator/developer standards
- `docs/runbooks/README.md` for operator runbook taxonomy
- `docs/contracts/README.md` for machine-readable workflow and release schema
  contracts
- `docs/plan/PLAN.md` plus the green-field program/router docs for active
  planning and traceability
- `docs/history/README.md` for archived material only

## Docs Sync Rules

- If behavior, contracts, workflows, or durable routing change, update the
  current canonical routers and affected authority docs in the same change set.
  The exact required router set is owned by
  `docs/standards/repository-engineering-standards.md`.
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
- `IDEMPOTENCY_ENABLED=true` requires `FILE_TRANSFER_CACHE_ENABLED=true` so
  `CACHE_REDIS_URL` is injected into the runtime task.
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
uv sync --locked --all-packages --all-extras --dev
uv lock --check
uv run ruff check .
uv run ruff check . --select I
uv run ruff format . --check
uv run ty check --force-exclude --error-on-warning packages scripts
uv run mypy
uv run pytest -q
uv run pytest -q \
  packages/nova_file_api/tests/test_generated_client_smoke.py
uv run python scripts/contracts/export_openapi.py --check
uv run python scripts/release/generate_runtime_config_contract.py --check
uv run python scripts/release/generate_clients.py --check
uv run python scripts/release/generate_python_clients.py --check
for p in packages/nova_file_api packages/nova_dash_bridge packages/nova_runtime_support; do uv build "$p"; done
```

Notes:

- `ty` is the canonical Python type gate for the full repo typing surface.
- `mypy` remains a required compatibility backstop on its narrower configured
  scope.
- `scripts/release/generate_clients.py --check` requires the repo-installed
  root npm toolchain; run `npm ci` before generated TypeScript SDK gates so the
  local `openapi-typescript` CLI is available without ad hoc network fetches.
- Use Node 24 LTS for local npm workspace commands that drive the TypeScript SDK
  and conformance lanes; CI/release workflows use the same baseline. The active
  workspace remains on the verified TypeScript 5.x line; TypeScript 6 is
  deferred until a dedicated repo-wide migration updates generated SDK output,
  conformance fixtures, and release/workflow docs together.
- `scripts/release/generate_python_clients.py --check` depends on the exact
  root dev dependency pin `openapi-python-client==0.28.3` plus the committed
  assets under `scripts/release/openapi_python_client/`. Treat generator-version
  bumps and template/config changes as coupled updates to docs, tests, and the
  committed SDK tree.
- `pyproject.toml` pins the supported `uv` CLI via
  `[tool.uv].required-version` (currently `0.11.1`); keep local tooling, CI,
  and docs aligned when bumping that version.
- Current manifest-owned runtime dependency floors are
  `pydantic-settings>=2.13.1` in the surviving runtime packages and
  `redis>=7.4.0` plus `uvicorn[standard]>=0.42.0` in
  `packages/nova_file_api`. If those floors move, update docs, lockfiles, and
  verification guidance in the same change.
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
- CI defaults to Python 3.13 for the primary lint/type/generation lane and
  keeps a Python 3.12 pytest/build compatibility lane for the surviving
  runtime packages.

### Pre-commit hooks

Install repo hooks with:

```bash
uv sync --locked --all-packages --all-extras --dev
uv run pre-commit install --install-hooks \
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
uv sync --locked --all-packages --all-extras --dev
uv run python scripts/conformance/check_typescript_module_policy.py
npm run -w @nova/sdk-file typecheck
npm run -w @nova/sdk-file build
npm run -w @nova/contracts-ts-conformance typecheck
npm run -w @nova/contracts-ts-conformance verify
uv run pytest -q scripts/release/tests/test_typescript_sdk_contracts.py
```

### R package artifacts, release packaging, or R SDK docs/contracts

Also run the shared R conformance entrypoint:

```bash
bash scripts/checks/run_sdk_conformance.sh
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
uv sync --locked --all-packages --all-extras --dev
uv run --with cfn-lint==1.46.0 cfn-lint infra/nova/*.yml infra/nova/deploy/*.yml infra/runtime/**/*.yml
uv run --with pytest pytest -q \
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
uv run pytest -q \
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
