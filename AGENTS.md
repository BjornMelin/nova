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
- Runtime deploy docs must describe bearer-verifier OIDC completeness as a
  Nova readiness/runtime contract. Do not move that enforcement back into
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
- Incomplete `OIDC_ISSUER`, `OIDC_AUDIENCE`, or `OIDC_JWKS_URL` must fail the
  `auth_dependency` readiness check.
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

Long-form gate expansion, toolchain baselines, focused pytest marker reruns,
manual hook policy, and SDK/runtime dependency-floor guidance are owned by
`docs/standards/repository-engineering-standards.md`.

Keep these repo-specific invariants in mind while using that matrix:

- `ty` is the canonical full-repo Python type gate; `mypy` remains the
  compatibility backstop.
- Current manifest-owned runtime dependency floors stay explicit in this file:
  `pydantic-settings>=2.13.1` in the surviving runtime packages, plus
  `redis>=7.4.0` and `uvicorn[standard]>=0.42.0` in `nova-file-api`.
- Runtime config authority is the pair
  `packages/nova_file_api/src/nova_file_api/config.py` plus
  `scripts/release/runtime_config_contract.py`, with
  `docs/release/runtime-config-contract.generated.md` as the generated
  operator-facing view.
- Use the quick route preflight above before broad runtime route edits.

### Pre-commit hooks

Install repo hooks with:

```bash
uv sync --locked --all-packages --all-extras --dev
uv run pre-commit install --install-hooks \
  --hook-type pre-commit --hook-type pre-push
```

If `uv` is not on `PATH`, install it first, then rerun
`scripts/dev/install_hooks.sh`.

Manual hook entrypoints and focused pytest marker reruns are documented in
`docs/standards/repository-engineering-standards.md`.

### OpenAPI, generated SDKs, npm packaging, or SDK docs/contracts

Also run the SDK/conformance expansion lanes from
`docs/standards/repository-engineering-standards.md`.

### R package artifacts, release packaging, or R SDK docs/contracts

Also run the R package and release-artifact conformance lanes from
`docs/standards/repository-engineering-standards.md`.

### Infra, workflows, or docs governance

Use the infra/docs governance expansion lanes from
`docs/standards/repository-engineering-standards.md`.

### Service Dockerfiles or release-image build flow

Use the release-image expansion lane from
`docs/standards/repository-engineering-standards.md`. Release-owned service
Dockerfiles stay under `apps/*`, and local image verification requires Docker
BuildKit plus `buildx`. Keep the canonical local commands:

```bash
docker buildx version
DOCKER_BUILDKIT=1 docker buildx build --load \
  -f apps/nova_file_api_service/Dockerfile \
  -t nova-file-api:test .
```

If the local Docker toolchain fails, use
`docs/runbooks/provisioning/docker-buildx-credential-helper-setup.md`.

### Downstream route or bridge contract changes

Spot check the Dash downstream consumer:

```bash
export DASH_PCA_REPO="${DASH_PCA_REPO:?set DASH_PCA_REPO to your dash-pca checkout}"
rg -n "/v1/transfers|/v1/jobs|nova_dash_bridge|nova_file_api" \
  "${DASH_PCA_REPO}"
```

## Documentation Rules

`docs/standards/repository-engineering-standards.md` owns the full docs-sync
policy, minimum router set, and contract-doc update matrix. When behavior,
contracts, workflows, or durable repo instructions change, update those router
docs and the affected authority docs in the same PR.

Historical retirement spot check:

```bash
rg -n "container-craft" README.md docs/architecture docs/plan docs/runbooks \
  | rg -v "docs/history|docs/architecture/adr/superseded|docs/architecture/spec/superseded|historical|archive|retired|ADR-0001|SPEC-0013|SPEC-0014|requirements.md|RELEASE-VERSION-MANIFEST"
```

## Local npm / CodeArtifact Rule

`docs/standards/repository-engineering-standards.md` owns the full repo-local
npm and CodeArtifact auth policy. Keep npm auth repo-scoped through the
committed `.npmrc`, the generated `.npmrc.codeartifact`, and
`npm run -s codeartifact:npm:env`. CI and release workflows must keep the
explicit `NPM_CONFIG_USERCONFIG` pattern; do not rely on global npm config
mutation.

## Deep References

- `docs/overview/NOVA-REPO-OVERVIEW.md`
- `docs/plan/PLAN.md`
- `docs/architecture/adr/index.md`
- `docs/architecture/spec/index.md`
- `docs/history/README.md` when tracing retired or superseded program archives
