# nova runtime

![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-0.129%2B-009688?logo=fastapi&logoColor=white) ![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1-6BA539?logo=openapiinitiative&logoColor=white)

FastAPI control-plane runtime for direct-to-S3 uploads/downloads and async job
orchestration. The service returns presigned metadata and job state; it does not
proxy file bytes.

## Start Here

Use these entrypoints before drilling into deeper docs:

- `AGENTS.md`: fresh-session operator guardrails and required checks
- `docs/README.md`: repo-wide documentation router
- `docs/architecture/README.md`: canonical architecture authority map
- `docs/standards/README.md`: deeper engineering standards and gate matrix
- `docs/runbooks/README.md`: release and operational runbooks

## Runtime Topology

- `packages/nova_file_api/`: transfer, jobs, readiness, metrics, ASGI
  entrypoint, worker orchestration, and **in-process bearer JWT** verification
  in the target architecture (`ADR-0033`, `SPEC-0027`)
- `packages/nova_dash_bridge/`: Dash/Flask/FastAPI integration adapters over
  `nova_file_api.public`
- `packages/nova_runtime_support/`: shared runtime support helpers
- `packages/contracts/`: OpenAPI artifacts and contract fixtures

## Contract Summary

Active route authority is the hard-cut canonical `/v1/*` surface plus
`/metrics/summary`.

Use the canonical authority chain:

- `docs/architecture/requirements.md`
- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `docs/architecture/spec/SPEC-0000-http-api-contract.md`
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `docs/architecture/spec/SPEC-0027-public-http-contract-revision-and-bearer-auth.md`

Green-field execution router: `docs/plan/greenfield-simplification-program.md`.

For the broader authority pack, use `docs/architecture/README.md`.

Active runtime topology and safety authority: `ADR-0025`, `ADR-0026`,
`SPEC-0017`, `SPEC-0018`, `SPEC-0019`, and `SPEC-0020`.
Active downstream validation authority: `ADR-0027`, `ADR-0028`, `ADR-0029`,
`SPEC-0021`, `SPEC-0022`, and `SPEC-0023`.

Public capabilities:

- transfer orchestration under `/v1/transfers/*`
- async job control plane under `/v1/jobs*`
- worker job completion via **direct persistence** (no public internal HTTP
  callback in the target architecture; `SPEC-0028`, `ADR-0035`)
- capability and release endpoints at `/v1/capabilities`,
  `/v1/resources/plan`, and `/v1/releases/info`
- operational health at `/v1/health/live` and `/v1/health/ready`
- operational summary at `/metrics/summary`

There is **no** separate `/v1/token/verify` or `/v1/token/introspect` surface in
the target architecture.

Do not add compatibility aliases or retired legacy route families.

`nova_dash_bridge` is an adapter-only seam. Browser and framework integrations
must forward bearer auth to canonical `/v1/transfers` and `/v1/jobs` routes and
must not rely on `session_id`, `X-Session-Id`, or `X-Scope-Id` as auth inputs.

## SDK and OpenAPI Posture

Nova owns the SDK contract surface:

- Python is the release-grade public SDK
- TypeScript is release-grade within Nova's existing CodeArtifact staged/prod
  system, generator-owned and subpath-only, on `openapi-typescript` +
  `openapi-fetch` per `ADR-0038` / `SPEC-0029`
- R is a first-class internal release artifact line with real R packages,
  logical format `r`, CodeArtifact generic package transport, and signed
  tarball evidence
- `docs/clients/README.md` stays secondary and is not the primary SDK release
  authority

OpenAPI 3.1 emitted from runtime code is the contract source for docs and SDK
generation. Runtime contract tests enforce stable snake_case `operationId`
values and semantic tags for public grouping.

For detailed SDK governance and generation rules, use:

- `docs/standards/repository-engineering-standards.md`
- `docs/architecture/spec/SPEC-0029-sdk-architecture-and-artifact-contract.md`
- `docs/architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`

## Key Runtime Invariants

- `POST /v1/jobs` publish failures return `503` with
  `error.code = "queue_unavailable"`
- idempotent mutation entrypoints use `IDEMPOTENCY_ENABLED` plus bounded TTL
  settings; when enabled, Nova requires a shared Redis claim storage and returns
  `503` with `error.code = "idempotency_unavailable"` if that shared store is
  unavailable; if execution succeeded before replay persistence failed, Nova
  keeps the existing claim so retries with the same key do not re-run the
  mutation
- `/v1/health/ready` gates traffic on `bucket_configured`,
  `auth_dependency`, and active runtime dependencies; `shared_cache` gates
  readiness only when idempotency is enabled, while `activity_store` remains a
  diagnostic check
- `AUTH_MODE=jwt_local` with incomplete OIDC settings leaves
  `auth_dependency` not-ready
- runtime CloudFormation defaults remain template-validation safe; incomplete
  `jwt_local` OIDC values fail Nova readiness rather than CloudFormation
  parameter validation
- terminal worker updates that set `status=succeeded` **must** normalize `error`
  to `null` (direct persistence path; `SPEC-0028`)
- `JOBS_RUNTIME_MODE=worker` is the shared-persistence runtime: workers require
  SQS delivery plus DynamoDB-backed job and activity tables
- malformed worker queue messages are retried through SQS redrive and are not
  acknowledged immediately

## Local Development

Baseline local gates:

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
source .venv/bin/activate && uv run python scripts/release/generate_runtime_config_contract.py --check
source .venv/bin/activate && uv run python scripts/release/generate_clients.py --check
source .venv/bin/activate && uv run python scripts/release/generate_python_clients.py --check
```

Tooling notes:

- Nova pins the supported `uv` CLI via `[tool.uv].required-version`; keep local
  tooling and CI on that exact version when changing the Python workspace
  contract.
- Pytest runs in `--import-mode=importlib` against editable workspace installs.
  Do not reintroduce repo-level `pythonpath` shims unless a new test failure
  proves they are required.

Runtime deploy/config drift guard:

- `packages/nova_file_api/src/nova_file_api/config.py` is the typed runtime
  source of truth.
- `scripts/release/runtime_config_contract.py` adds the curated deploy/template
  metadata that cannot be inferred from `Settings` alone.
- `docs/release/runtime-config-contract.generated.md` is the generated
  operator-facing matrix. Refresh it with
  `scripts/release/generate_runtime_config_contract.py`.

Canonical typing gates:

```bash
source .venv/bin/activate && uv run ty check --force-exclude --error-on-warning packages scripts
source .venv/bin/activate && uv run mypy
```

`ty` is the required full-repo type gate. `mypy` remains a required
compatibility backstop on its narrower configured scope.

Package/app build verification:

```bash
source .venv/bin/activate && \
for p in packages/nova_file_api packages/nova_dash_bridge; do uv build "$p"; done
```

If you touch `packages/nova_runtime_support`, also run:

```bash
source .venv/bin/activate && uv build packages/nova_runtime_support
```

## Pre-commit hooks

Install the repo hooks with:

```bash
source .venv/bin/activate && uv sync --locked
source .venv/bin/activate && uv run pre-commit install --install-hooks \
  --hook-type pre-commit --hook-type pre-push
```

If `uv` is not on your shell `PATH`, install it first, then rerun
`scripts/dev/install_hooks.sh`.

Useful manual hook entrypoints:

```bash
source .venv/bin/activate && uv run pre-commit run typing-gates --hook-stage manual -a
source .venv/bin/activate && uv run pre-commit run quality-gates --hook-stage manual -a
source .venv/bin/activate && uv run pre-commit run sdk-conformance --hook-stage manual -a
source .venv/bin/activate && uv run pre-commit run infra-contracts --hook-stage manual -a
source .venv/bin/activate && uv run pre-commit run docker-release-images --hook-stage manual -a
```

## Repo-Local npm / CodeArtifact Auth

Keep npm auth repo-scoped:

```bash
cd <NOVA_REPO_ROOT>
eval "$(npm run -s codeartifact:npm:env)"
npm install --no-package-lock
```

The helper writes `.npmrc.codeartifact` and sets `NPM_CONFIG_USERCONFIG` so
other repos stay untouched. It also exports `NPM_REGISTRY_URL` for npm publish
and smoke-test steps. CI uses the same explicit `NPM_CONFIG_USERCONFIG`
pattern with a temporary npmrc, so Nova does not rely on
`aws codeartifact login --tool npm` or global `~/.npmrc` mutation.

Release automation note: `Publish Packages` is the manual staging publish
workflow for Python, TypeScript/npm, and R artifacts, and `Promote Prod` is
the manual prod promotion workflow for those staged, gate-validated artifacts.

## Release and Operations

Use `docs/runbooks/README.md` as the canonical runbook entrypoint.

Key release docs:

- `docs/runbooks/release/release-runbook.md`
- `docs/runbooks/release/release-policy.md`
- `docs/runbooks/release/nonprod-live-validation-runbook.md`
- `docs/runbooks/release/release-promotion-dev-to-prod.md`
- `docs/runbooks/provisioning/deploy-runtime-cloudformation-environments.md`
- `docs/runbooks/provisioning/docker-buildx-credential-helper-setup.md`

The runtime deploy operator now owns the ECS service task role and cache secret
wiring. Do not supply `TASK_ROLE_ARN`,
`TASK_EXECUTION_SECRET_ARNS`, or `TASK_EXECUTION_SSM_PARAMETER_ARNS`.

## Local Service Images

Local service-image verification uses the release-owned Dockerfiles under
`apps/*` and now requires Docker BuildKit plus `buildx`.

See:

- `docs/runbooks/provisioning/docker-buildx-credential-helper-setup.md`

## Historical and Archive Paths

Active docs stay under the root `docs/**` tree.
Historical and superseded materials belong under:

- `docs/history/**`
- `docs/architecture/adr/superseded/**`
- `docs/architecture/spec/superseded/**`
