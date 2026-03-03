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

## Active Authority

Use these as the active authority set:

- `docs/PRD.md`
- `docs/architecture/requirements.md`
- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `docs/architecture/spec/SPEC-0000-http-api-contract.md`
- `docs/architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md`
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `docs/plan/PLAN.md`
- `docs/runbooks/README.md`

Historical-only pointers:

- `PRD.md`
- `FINAL-PLAN.md`
- `docs/plan/HISTORY-INDEX.md`
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

Disallowed runtime route families:

- `/api/*`
- `/api/v1/*`
- `/healthz`
- `/readyz`

Do not add compatibility aliases or namespace shims.

Required route verification command:

```bash
source .venv/bin/activate && \
rg -n "/v1/transfers|/v1/jobs|/v1/internal/jobs|/v1/capabilities|/v1/resources/plan|/v1/releases/info|/v1/health/live|/v1/health/ready|/metrics/summary" apps packages docs
```

## Runtime Invariants

- `POST /v1/jobs` queue publish failures MUST return `503` with
  `error.code = "queue_unavailable"`.
- Failed enqueue responses MUST NOT be idempotency replay cached.
- `/v1/health/ready` must evaluate only traffic-critical dependencies.
- Missing/blank `FILE_TRANSFER_BUCKET` MUST fail readiness.
- `POST /v1/internal/jobs/{job_id}/result` with `status=succeeded` MUST clear
  `error` to `null`.
- Do not log presigned URLs, JWTs, or signed query values.
- Do not run synchronous JWT verification directly on async event-loop paths;
  use a threadpool boundary.
- `JOBS_QUEUE_BACKEND=sqs` with `JOBS_ENABLED=true` requires
  `JOBS_SQS_QUEUE_URL`.
- `ACTIVITY_STORE_BACKEND=dynamodb` requires `ACTIVITY_ROLLUPS_TABLE`.

## Required Quality Gates

Always run from repository root with `.venv` active.

```bash
source .venv/bin/activate && uv lock --check
source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .
source .venv/bin/activate && uv run mypy
source .venv/bin/activate && uv run pytest -q
source .venv/bin/activate && uv run pytest -q \
  packages/nova_file_api/tests/test_generated_client_smoke.py
source .venv/bin/activate && \
for p in packages/nova_file_api packages/nova_auth_api \
  packages/nova_dash_bridge apps/nova_file_api_service \
  apps/nova_auth_api_service; do uv build "$p"; done
```

## Documentation Update Rules

Any behavioral or contract change MUST update all affected docs in the same PR:

- `README.md`
- `docs/PRD.md`
- `docs/architecture/requirements.md`
- affected `docs/architecture/adr/*.md`
- affected `docs/architecture/spec/*.md`
- `docs/plan/PLAN.md`
- affected `docs/plan/release/*.md`
- `docs/runbooks/README.md` when runbook authority changes
- `docs/history/**` when archival paths/evidence pointers change
- `PRD.md` and `FINAL-PLAN.md` only when archive pointers change

## Cross-Repo Check (dash-pca)

Path: `~/repos/work/pca-analysis-dash/dash-pca`

```bash
rg -n "/v1/transfers|/v1/jobs|nova_dash_bridge|nova_file_api" \
  ~/repos/work/pca-analysis-dash/dash-pca
```

## Historical Retirement Check

```bash
rg -n "container-craft" AGENTS.md README.md docs/architecture docs/plan docs/runbooks \
  | rg -v "docs/history|historical|archive|retired|ADR-0014|SPEC-0013|SPEC-0014|requirements.md|RELEASE-VERSION-MANIFEST"
```
