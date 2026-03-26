# AGENTS.md (nova runtime)

## Purpose

Nova is the runtime monorepo for the file-transfer API: transfers, jobs, and
related surfaces, with **bearer JWT** verification in-process (`ADR-0033`,
`SPEC-0027`), no separate auth service, and adapter packages for consumers.

**Audience:** coding agents and contributors. This file holds **commands,
guardrails, and invariants**. Deeper matrices and policies live in
[docs/standards/repository-engineering-standards.md](docs/standards/repository-engineering-standards.md).

**Entry:** Read this file first. Use
[docs/README.md](docs/README.md) next to navigate the rest of `docs/`.

## Onboarding (read in order)

| Step | Document | Use for |
| --- | --- | --- |
| 1 | This file (`AGENTS.md`) | Commands, non-negotiables, task router |
| 2 | [docs/README.md](docs/README.md) | Documentation map and where to look next |
| 3 | [docs/architecture/README.md](docs/architecture/README.md) | Route chain, architecture packs, deploy governance |
| 4 | [README.md](README.md) | Repo overview and quick local setup |
| 5 | [docs/standards/README.md](docs/standards/README.md) | Standards index |
| 6 | [docs/standards/repository-engineering-standards.md](docs/standards/repository-engineering-standards.md) | Full quality-gate matrix, docs-sync rules, npm/CodeArtifact |
| 7 | [docs/runbooks/README.md](docs/runbooks/README.md) | Release and operations (when the task touches deploy or ops) |

**Other routers (open when the task matches):**

- [docs/contracts/README.md](docs/contracts/README.md) — workflow and release **schema** contracts.
- [docs/plan/PLAN.md](docs/plan/PLAN.md) — active planning and traceability.
- [docs/history/README.md](docs/history/README.md) — **archived** material only.

This repository uses **one root `AGENTS.md`**. Do not add nested `AGENTS.md`
files unless a directory-local rule is durable and materially different.

## Repository layout

| Path | Role |
| --- | --- |
| [packages/nova_file_api/](packages/nova_file_api/) | Transfers, jobs, readiness, metrics, ASGI entrypoint, workers, bearer JWT verification (`ADR-0033`, `SPEC-0027`). |
| [packages/nova_dash_bridge/](packages/nova_dash_bridge/) | Dash / Flask / FastAPI adapters over `nova_file_api.public`. |
| [packages/nova_runtime_support/](packages/nova_runtime_support/) | Outer-ASGI request context, shared FastAPI exception registration, log redaction, shared auth helpers. |
| [packages/contracts/](packages/contracts/) | OpenAPI artifacts and contract inputs. |

**Packaging:** Each runtime package must declare explicit intra-workspace runtime dependencies in its own `pyproject.toml`. Do not rely on root workspace sync/install shape as a production contract.

## SDK and OpenAPI

Public SDKs exist for Python, TypeScript, and R. Python is the primary
externally supported SDK. **Generation** is pinned to `openapi-python-client==0.28.3` with config under
[scripts/release/openapi_python_client/](scripts/release/openapi_python_client/).
Fix generator output via OpenAPI producers, committed OpenAPI,
[scripts/release/generate_clients.py](scripts/release/generate_clients.py),
generator config, and minimal templates — **not** large post-generation patches.

**Detail:** TypeScript layout, R packages, generator ownership, and TS/R
**do-not** lists are in
[Generated TypeScript SDK Rules](docs/standards/repository-engineering-standards.md#generated-typescript-sdk-rules),
[R Package Rules](docs/standards/repository-engineering-standards.md#r-package-rules), and
[Generator Ownership Rules](docs/standards/repository-engineering-standards.md#generator-ownership-rules).

TypeScript SDK operator rules that must remain true:

- public packages must not expose package-root `"."` exports
- TypeScript SDK packages stay generator-owned and subpath-only
- internal-only surfaces require `x-nova-sdk-visibility: internal`
- generate and validate TypeScript SDK outputs through
  `scripts/release/generate_clients.py`
- publish and install paths must preserve the CodeArtifact staged/prod split
- npm auth lanes must set `NPM_CONFIG_USERCONFIG`
- keep `docs/standards/README.md` aligned when these rules change

## Documentation and behavior changes

When behavior, contracts, workflows, or durable routing change, update the
routers and authority docs **in the same change set**. The required router set
and update matrix are defined in
[Documentation Synchronization Rules](docs/standards/repository-engineering-standards.md#documentation-synchronization-rules).

- Bridge or browser auth: keep guidance aligned on the bearer-only
  `nova_dash_bridge` → `nova_file_api.public` seam and on `/v1/transfers` and
  `/v1/jobs`.
- Runtime deploy docs: describe OIDC completeness for the bearer verifier as a
  readiness/runtime contract; do not move that into CloudFormation template
  validation alone.
- Outer ASGI and errors: [packages/nova_runtime_support/](packages/nova_runtime_support/)
  owns outer-ASGI request context and shared exception registration.
  `nova_dash_bridge.create_fastapi_router()` stays route-only; standalone
  FastAPI hosts install the shared stack explicitly.
- `nova_file_api.public` stays **async-first**; FastAPI calls it directly. Sync
  wrappers are only for true sync hosts (e.g. Flask/Dash).
- Do not document `session_id`, `X-Session-Id`, or `X-Scope-Id` as public auth
  inputs in downstream consumer docs.

**npm / CodeArtifact:** Repo-scoped auth, `.npmrc`, and CI patterns are in
[Repo-Local npm and CodeArtifact Auth](docs/standards/repository-engineering-standards.md#repo-local-npm-and-codeartifact-auth).

## Canonical guardrails

- Public HTTP surface: `/v1/*` and `/metrics/summary`. Health: `/v1/health/live`,
  `/v1/health/ready`.
- Callers authenticate with **bearer JWT** verified in `nova_file_api`. There
  is no `/v1/token/verify` or `/v1/token/introspect` (`ADR-0033`, `ADR-0034`,
  `SPEC-0027`).
- Do not add compatibility aliases for legacy API-prefixed routes or shorthand
  health/readiness endpoints.
- `nova_dash_bridge` forwards context and calls `nova_file_api.public`; it does
  not redefine routes, auth, or storage.
- `nova_file_api.public` is the in-process transfer API: plain-data factory/config,
  async-first; no public `BaseSettings` synthesis; no bridge-local
  sync-over-async threadpools for FastAPI.
- FastAPI apps that need Nova request-id and error envelopes must use the
  outer-ASGI wrapper and exception registration from `nova_runtime_support`.
- **OpenAPI 3.1** from runtime code is the source for docs and SDKs. Keep
  `operationId` stable `snake_case` and tags consistent with contract tests.
  Custom `openapi_extra` body `$ref` values must resolve to named components.
- Compatibility: [packages/nova_file_api/tests/test_generated_client_smoke.py](packages/nova_file_api/tests/test_generated_client_smoke.py).
- Never log presigned URLs, JWTs, or signed query parameters.
- Local audit tracking: keep `.agents/AUDIT_DELIVERABLES/*` locally if needed;
  do not commit it.

**Route sweep before large edits to routes:**

```bash
rg -n "/v1/transfers|/v1/jobs|/v1/capabilities|/v1/resources/plan|/v1/releases/info|/v1/health/live|/v1/health/ready|/metrics/summary" packages docs
```

## Runtime invariants

### HTTP errors and idempotency

- `POST /v1/jobs`: queue publish failure → `503`, `error.code = "queue_unavailable"`.
- Idempotent mutations need a shared Redis claim store; store failure → `503`,
  `error.code = "idempotency_unavailable"` (no silent local fallback).
- Do not cache failed enqueue responses for idempotency replay.
- Idempotency env: `IDEMPOTENCY_ENABLED`, `IDEMPOTENCY_TTL_SECONDS` only; do not
  add or document `IDEMPOTENCY_MODE`.
- `IDEMPOTENCY_ENABLED=true` implies `FILE_TRANSFER_CACHE_ENABLED=true` so
  `CACHE_REDIS_URL` is available to the task.

### Readiness and auth

- `/v1/health/ready` returns `503` when a traffic-critical check fails.
- Missing or blank `FILE_TRANSFER_BUCKET` fails readiness.
- Incomplete `OIDC_ISSUER`, `OIDC_AUDIENCE`, or `OIDC_JWKS_URL` fails the
  `auth_dependency` readiness check.
- Shared cache gates readiness only when idempotency is enabled; activity-store
  health is visible but not readiness-fatal.
- Prefer async JWT verification in `nova_file_api` (`ADR-0033`, `ADR-0037`);
  any sync verification on async paths uses a threadpool (`ADR-0026`,
  `SPEC-0019`).

### Jobs, queue, and DynamoDB

- `JOBS_QUEUE_BACKEND=sqs` with `JOBS_ENABLED=true` requires `JOBS_SQS_QUEUE_URL`.
- `JOBS_REPOSITORY_BACKEND=dynamodb` requires `JOBS_DYNAMODB_TABLE`.
- Job listing uses the `scope_id-created_at-index` GSI; do not `Scan`.
- `JOBS_RUNTIME_MODE=worker` requires `JOBS_ENABLED=true`,
  `JOBS_QUEUE_BACKEND=sqs`, `JOBS_SQS_QUEUE_URL`,
  `JOBS_REPOSITORY_BACKEND=dynamodb`, `JOBS_DYNAMODB_TABLE`,
  `ACTIVITY_STORE_BACKEND=dynamodb`, and `ACTIVITY_ROLLUPS_TABLE`.
- Direct persistence (`SPEC-0028`): worker terminal `status=succeeded` clears
  `error` to `null`. HTTP callbacks (`JOBS_API_BASE_URL`,
  `JOBS_WORKER_UPDATE_TOKEN`) are not part of the target model once direct
  persistence applies (`SPEC-0028`).
- Malformed worker messages stay unacked so SQS retry/DLQ handles poison messages.

### Activity and deploy scripts

- `ACTIVITY_STORE_BACKEND=dynamodb` requires `ACTIVITY_ROLLUPS_TABLE`.
- ECS task role and cache secrets are owned by the runtime stack. Do **not** pass
  `TASK_ROLE_ARN`, `TASK_EXECUTION_SECRET_ARNS`, or
  `TASK_EXECUTION_SSM_PARAMETER_ARNS` into
  [scripts/release/deploy-runtime-cloudformation-environment.sh](scripts/release/deploy-runtime-cloudformation-environment.sh).

## Verification (task router)

Run the **baseline** below for most changes. For more lanes (markers, hooks,
toolchain notes), see
[Quality-Gate Matrix](docs/standards/repository-engineering-standards.md#quality-gate-matrix).

**Baseline:**

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

### If you changed … then also run …

| Area | See standards section |
| --- | --- |
| OpenAPI, generated TS SDK, npm packaging, SDK docs/contracts | [Quality-Gate Matrix](docs/standards/repository-engineering-standards.md#quality-gate-matrix) (npm/TS gates); [Generated TypeScript SDK Rules](docs/standards/repository-engineering-standards.md#generated-typescript-sdk-rules) |
| R packages or R release artifacts | [Quality-Gate Matrix](docs/standards/repository-engineering-standards.md#quality-gate-matrix) (R gates); [R Package Rules](docs/standards/repository-engineering-standards.md#r-package-rules) |
| Infra, workflows, docs governance | [Quality-Gate Matrix](docs/standards/repository-engineering-standards.md#quality-gate-matrix) (infra/docs gates) |
| Service Dockerfiles or release images | Manual hook / `scripts/checks/run_docker_release_images.sh` ([Workflow Mapping](docs/standards/repository-engineering-standards.md#workflow-mapping), [Pre-commit Policy](docs/standards/repository-engineering-standards.md#pre-commit-policy)) |
| Bridge or downstream routes | [Downstream and Retirement Spot Checks](docs/standards/repository-engineering-standards.md#downstream-and-retirement-spot-checks); optional `rg` below |

**Tooling notes (baseline context):**

- `ty` is the full-repo type gate; `mypy` is the compatibility backstop.
- Runtime dependency floors include `pydantic-settings>=2.13.1` (relevant
  packages), plus `redis>=7.4.0` and `uvicorn[standard]>=0.42.0` in
  `nova-file-api`.
- Runtime config: [packages/nova_file_api/src/nova_file_api/config.py](packages/nova_file_api/src/nova_file_api/config.py) and
  [scripts/release/runtime_config_contract.py](scripts/release/runtime_config_contract.py);
  generated operator view:
  [docs/release/runtime-config-contract.generated.md](docs/release/runtime-config-contract.generated.md).

### Pre-commit

```bash
uv sync --locked --all-packages --all-extras --dev
uv run pre-commit install --install-hooks \
  --hook-type pre-commit --hook-type pre-push
```

If `uv` is missing from `PATH`, install it, then run
[scripts/dev/install_hooks.sh](scripts/dev/install_hooks.sh).

Manual hook names and marker-based pytest reruns:
[Pre-commit Policy](docs/standards/repository-engineering-standards.md#pre-commit-policy).

### Service image (local)

```bash
docker buildx version
DOCKER_BUILDKIT=1 docker buildx build --load \
  -f apps/nova_file_api_service/Dockerfile \
  -t nova-file-api:test .
```

This local image-build contract requires BuildKit plus `buildx`.

If Docker auth to registries fails, see
[docs/runbooks/provisioning/docker-buildx-credential-helper-setup.md](docs/runbooks/provisioning/docker-buildx-credential-helper-setup.md).

### Optional downstream spot check

```bash
export DASH_PCA_REPO="${DASH_PCA_REPO:?set DASH_PCA_REPO to your dash-pca checkout}"
rg -n "/v1/transfers|/v1/jobs|nova_dash_bridge|nova_file_api" \
  "${DASH_PCA_REPO}"
```

### Optional retirement hygiene

```bash
rg -n "container-craft" README.md docs/architecture docs/plan docs/runbooks \
  | rg -v "docs/history|docs/architecture/adr/superseded|docs/architecture/spec/superseded|historical|archive|retired|ADR-0001|SPEC-0013|SPEC-0014|requirements.md|RELEASE-VERSION-MANIFEST"
```

## Further reading

- [docs/overview/NOVA-REPO-OVERVIEW.md](docs/overview/NOVA-REPO-OVERVIEW.md)
- [docs/plan/PLAN.md](docs/plan/PLAN.md)
- [docs/architecture/adr/index.md](docs/architecture/adr/index.md)
- [docs/architecture/spec/index.md](docs/architecture/spec/index.md)
- [docs/history/README.md](docs/history/README.md) — retired or superseded programs only
