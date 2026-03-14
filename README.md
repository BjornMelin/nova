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
  entrypoint, and worker
  orchestration
- `packages/nova_auth_api/`: token verify/introspect semantics and ASGI
  entrypoint
- `packages/nova_dash_bridge/`: Dash/Flask/FastAPI integration adapters
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

For the broader authority pack, use `docs/architecture/README.md`.

Active runtime topology and safety authority: `ADR-0025`, `ADR-0026`,
`SPEC-0017`, `SPEC-0018`, `SPEC-0019`, and `SPEC-0020`.
Active downstream validation authority: `ADR-0027`, `ADR-0028`, `ADR-0029`,
`SPEC-0021`, `SPEC-0022`, and `SPEC-0023`.

Public capabilities:

- transfer orchestration under `/v1/transfers/*`
- async job control plane under `/v1/jobs*`
- internal worker result updates at `/v1/internal/jobs/{job_id}/result`
- capability and release endpoints at `/v1/capabilities`,
  `/v1/resources/plan`, and `/v1/releases/info`
- operational health at `/v1/health/live` and `/v1/health/ready`
- operational summary at `/metrics/summary`

Do not add compatibility aliases or retired legacy route families.

## SDK and OpenAPI Posture

Nova owns the SDK contract surface:

- Python is the release-grade public SDK
- TypeScript remains generated/private-distribution contract surface
- R scaffolding remains in-repo for parity and must not be deleted

OpenAPI 3.1 emitted from runtime code is the contract source for docs and SDK
generation. Runtime contract tests enforce stable snake_case `operationId`
values and semantic tags for public grouping.

For detailed SDK governance and generation rules, use:

- `docs/standards/repository-engineering-standards.md`
- `docs/architecture/spec/SPEC-0011-multi-language-sdk-architecture-and-package-map.md`
- `docs/architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`

## Key Runtime Invariants

- `POST /v1/jobs` publish failures return `503` with
  `error.code = "queue_unavailable"`
- strict distributed idempotency outages return `503` with
  `error.code = "idempotency_unavailable"` for guarded mutation entrypoints
- `/v1/health/ready` is dependency-scoped and fails on blank
  `FILE_TRANSFER_BUCKET`
- `AUTH_MODE=jwt_local` with incomplete OIDC settings leaves
  `auth_dependency` not-ready
- `POST /v1/internal/jobs/{job_id}/result` with `status=succeeded` normalizes
  `error` to `null`
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
source .venv/bin/activate && uv run python scripts/release/generate_clients.py --check
source .venv/bin/activate && uv run python scripts/release/generate_python_clients.py --check
```

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
for p in packages/nova_file_api packages/nova_auth_api \
  packages/nova_dash_bridge; do uv build "$p"; done
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
other repos stay untouched. npm 10.x requires AWS CLI `v2.9.5 or newer` when
ephemeral CI shells use `aws codeartifact login --tool npm`. Do not run
`aws codeartifact login --tool npm` on a developer workstation because it
rewrites global `~/.npmrc`.

## Release and Operations

Use `docs/runbooks/README.md` as the canonical runbook entrypoint.

Key release docs:

- `docs/plan/release/RELEASE-RUNBOOK.md`
- `docs/plan/release/RELEASE-POLICY.md`
- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- `docs/plan/release/release-promotion-dev-to-prod-guide.md`
- `docs/plan/release/deploy-runtime-cloudformation-environments-guide.md`
- `docs/plan/release/docker-buildx-and-credential-helper-setup-guide.md`

## Local Service Images

Local service-image verification uses the release-owned Dockerfiles under
`apps/*` and now requires Docker BuildKit plus `buildx`.

See:

- `docs/plan/release/docker-buildx-and-credential-helper-setup-guide.md`

## Historical and Archive Paths

Active docs stay under the root `docs/**` tree.
Historical and superseded materials belong under:

- `docs/history/**`
- `docs/architecture/adr/superseded/**`
- `docs/architecture/spec/superseded/**`
- `docs/plan/HISTORY-INDEX.md`
