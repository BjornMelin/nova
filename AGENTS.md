# AGENTS.md (nova runtime)

Nova is the canonical runtime monorepo for the file-transfer API, auth API, and
their adapter surfaces.

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
  entrypoint, and worker
  orchestration.
- `packages/nova_auth_api/`: token verify/introspect semantics and ASGI
  entrypoint.
- `packages/nova_dash_bridge/`: Dash/Flask/FastAPI integration adapters.
- `packages/nova_runtime_support/`: shared runtime support helpers.
- `packages/contracts/`: OpenAPI artifacts and contract inputs.

Workspace packaging rules:

- Runtime packages must declare explicit intra-workspace runtime dependencies in
  their own `pyproject.toml` files.
- Do not rely on root workspace sync/install shape as an implicit production
  contract.

SDK posture:

- Nova must provide complete public SDKs for Python, TypeScript, and R.
- Python is the release-grade public SDK surface.
- TypeScript remains generated/private-distribution contract surface.
- R scaffolding stays in-repo and must not be deleted.
- Internal-only operations remain excluded from public SDK generation.
- Generated TypeScript SDKs remain validation-free private-distribution artifacts in this wave.
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

## Canonical Guardrails

- Public runtime routes are canonical `/v1/*` plus `/metrics/summary`.
- Auth API routes are `/v1/token/verify`, `/v1/token/introspect`,
  `/v1/health/live`, and `/v1/health/ready`.
- Do not add compatibility aliases or namespace shims such as `/api/*`,
  `/api/v1/*`, `/healthz`, or `/readyz`.
- `nova_dash_bridge` is an adapter package. It may forward context and call
  canonical Nova contracts, but it must not redefine route, auth, or storage
  authority.
- OpenAPI 3.1 emitted from runtime code is the contract source for docs and SDK
  generation.
- OpenAPI `operationId` values must remain stable snake_case names, and tags
  must remain semantic groupings used by the contract tests.
- Custom request-body `$ref` values injected through `openapi_extra` must
  resolve to named component schemas in emitted OpenAPI.
- Generated-client compatibility is enforced by
  `packages/nova_file_api/tests/test_generated_client_smoke.py`.
- Never log presigned URLs, JWTs, or signed query values.

Quick route preflight:

```bash
source .venv/bin/activate && \
rg -n "/v1/transfers|/v1/jobs|/v1/internal/jobs|/v1/capabilities|/v1/resources/plan|/v1/releases/info|/v1/token/verify|/v1/token/introspect|/v1/health/live|/v1/health/ready|/metrics/summary" packages docs
```

## Runtime Invariants

- `POST /v1/jobs` queue publish failures must return `503` with
  `error.code = "queue_unavailable"`.
- Mutation entrypoints running with idempotency currently use the two-tier
  cache and may fall back to local claim handling when the shared cache errors.
- Failed enqueue responses must not be idempotency replay cached.
- `IDEMPOTENCY_ENABLED` and `IDEMPOTENCY_TTL_SECONDS` are the current
  idempotency settings surface; deploy and operator docs must not claim
  `IDEMPOTENCY_MODE` support until runtime semantics exist.
- `/v1/health/ready` currently returns `503` when any reported readiness check
  is false.
- Missing or blank `FILE_TRANSFER_BUCKET` must fail readiness.
- `AUTH_MODE=jwt_local` with incomplete `OIDC_ISSUER`, `OIDC_AUDIENCE`, or
  `OIDC_JWKS_URL` must fail the `auth_dependency` readiness check.
- Do not run synchronous JWT verification directly on async event-loop paths;
  use a threadpool boundary.
- `POST /v1/internal/jobs/{job_id}/result` with `status=succeeded` must clear
  `error` to `null`.
- `JOBS_QUEUE_BACKEND=sqs` with `JOBS_ENABLED=true` requires
  `JOBS_SQS_QUEUE_URL`.
- `JOBS_REPOSITORY_BACKEND=dynamodb` requires `JOBS_DYNAMODB_TABLE`.
- DynamoDB-backed job listing requires the
  `scope_id-created_at-index` GSI; do not fall back to `Scan`.
- `JOBS_RUNTIME_MODE=worker` requires `JOBS_ENABLED=true`,
  `JOBS_QUEUE_BACKEND=sqs`, `JOBS_SQS_QUEUE_URL`, `JOBS_API_BASE_URL`, and
  `JOBS_WORKER_UPDATE_TOKEN`.
- Malformed worker queue messages must remain unacked so SQS retry/DLQ policy
  handles poison messages.
- `ACTIVITY_STORE_BACKEND=dynamodb` requires `ACTIVITY_ROLLUPS_TABLE`.

## Task Router

Use the baseline gates for most code changes, then expand based on what you
touched.

### Runtime code under runtime packages

Run:

```bash
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
source .venv/bin/activate && uv run python scripts/release/generate_clients.py --check
source .venv/bin/activate && uv run python scripts/release/generate_python_clients.py --check
source .venv/bin/activate && \
for p in packages/nova_file_api packages/nova_auth_api \
  packages/nova_dash_bridge; do uv build "$p"; done
```

Notes:

- `ty` is the canonical Python type gate for the full repo typing surface.
- `mypy` remains a required compatibility backstop on its narrower configured
  scope.
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
`.github/workflows/conformance-clients.yml`:

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
`apps/nova_auth_api_service/Dockerfile`, `buildspecs/buildspec-release.yml`, or
release-image documentation:

```bash
docker buildx version
DOCKER_BUILDKIT=1 docker buildx build --load \
  -f apps/nova_file_api_service/Dockerfile \
  -t nova-file-api:test .
DOCKER_BUILDKIT=1 docker buildx build --load \
  -f apps/nova_auth_api_service/Dockerfile \
  -t nova-auth-api:test .
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
  `docs/plan/release/docker-buildx-and-credential-helper-setup-guide.md`.

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
  helper exports `NPM_CONFIG_USERCONFIG` to that path.
- If you switch AWS accounts or CodeArtifact targets, set `AWS_REGION`,
  `CODEARTIFACT_DOMAIN`, and/or `CODEARTIFACT_STAGING_REPOSITORY` before
  running the helper.
- Do not run `aws codeartifact login --tool npm` on a developer workstation.
  It rewrites global `~/.npmrc`.
- npm 10.x requires AWS CLI v2.9.5 or newer when ephemeral CI shells use that
  command.

## Deep References

- `docs/overview/NOVA-REPO-OVERVIEW.md`
- `docs/plan/PLAN.md`
- `docs/architecture/adr/index.md`
- `docs/architecture/spec/index.md`
- `docs/plan/HISTORY-INDEX.md` when tracing retired or superseded guidance
