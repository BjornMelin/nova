# AGENTS.md (nova runtime)

This repository is the canonical runtime monorepo for file-transfer and
auth API services. Active infrastructure and deployment authority is owned in
this repository under `infra/nova/**` and `infra/runtime/**`. Historical
cross-repo migration evidence remains in docs for prior cutover phases, and
consumer migration work includes `~/repos/work/pca-analysis-dash/dash-pca`.

## Runtime Topology

- `apps/nova_file_api_service/`: ASGI wrapper for file API runtime.
- `apps/nova_auth_api_service/`: ASGI wrapper for auth API runtime.
- `packages/nova_file_api/`: transfer + async jobs control-plane package.
- `packages/nova_auth_api/`: token verify/introspect service package.
- `packages/nova_dash_bridge/`: Dash/Flask/FastAPI bridge adapters.
- `packages/contracts/`: OpenAPI and shared contract artifacts.
- `docs/architecture/`: requirements, ADRs, and SPECs.
- `docs/plan/`: execution plans, subplans, and triggers.
- `docs/plan/release/`: release notes, checklists, and runbooks.

## SKILLS AND TOOLS

### SKILLS

Use the best-fitting skills for each task. Prioritize this set:

- `$fastapi`
- `$openapi-spec-generation`
- `$architecture-decision-records`
- `$api-design-principles`
- `$python-anti-patterns`
- `$python-packaging`
- `$python-type-safety`
- `$python-code-style`
- `$python-testing-patterns`
- `$pytest-dev`
- `$uv-package-manager`

### TOOLS

Use tools intentionally:

- Context7:
  - `context7.resolve-library-id`: map library/package names to doc IDs.
  - `context7.query-docs`: fetch current API docs and snippets.
- gh_grep:
  - `gh_grep.searchGitHub`: find real code usage patterns.
- Exa:
  - `exa.web_search_advanced_exa`: targeted web research.
  - `exa.deep_researcher_start`: run deep research tasks.
  - `exa.deep_researcher_check`: poll until research is complete.
- Planning:
  - `functions.update_plan`: keep execution steps current.
- Source inspection:
  - `opensrc list` for installed dependency source paths.
  - inspect `opensrc/sources.json` for package/version/source location.

### Operational Mandate

Do not oversimplify or defer required features. If sources conflict, apply
the decision framework and use options scoring at least 9.0/10.0.
All code and docs must remain production-ready.

## Guardrails

- Use `FINAL-PLAN.md` as baseline historical execution source and
  `ADR-0015`/`SPEC-0015` as target-state implementation authority.
- Keep `docs/plan/PLAN.md` synchronized with current implementation state.
- Treat architecture state as dual-track until next feature branch delivery:
  - current implemented baseline: `SPEC-0000`, `SPEC-0003`, `SPEC-0004`,
    `SPEC-0008`
  - target-state contract for upcoming implementation:
    `ADR-0015`, `SPEC-0015`
- Treat OpenAPI as the contract and update SPEC/ADR docs first for
  contract-level changes.
- Keep generated-client smoke coverage working for contract changes
  (`test_generated_client_smoke.py`).
- Keep dependencies lean and maintained.
- Never log presigned URLs, JWTs, or signed query values.
- Never run synchronous JWT verification directly in async route/dependency
  code; use a threadpool boundary.

### Current Runtime Baseline Rules (Blocking Until Target PR Lands)

- Use only:
  - `/api/transfers/*`
  - `/api/jobs/*`
  - `/metrics/summary`
  - `/healthz`
  - `/readyz`
- Do not introduce deprecated alias routes or retired package/module names.
- Do not add compatibility alias routes or namespace shims.
- Fail reviews when legacy patterns are introduced.

Required verification command:

```bash
source .venv/bin/activate && \
rg -n "/api/transfers|/api/jobs|/metrics/summary|/healthz|/readyz" apps packages docs
```

### Next PR Target Contract Rules (Locked for Implementation Branch)

- Target API capabilities MUST be implemented under:
  - `/v1/jobs`
  - `/v1/jobs/{id}/events`
  - `/v1/capabilities`
  - `/v1/resources/plan`
  - `/v1/releases/info`
  - `/v1/health/live`
  - `/v1/health/ready`
- Do not introduce compatibility alias routes or namespace shims while
  delivering target-state cutover.
- Treat `SPEC-0015` as `Planned` authority until implementation merges, then
  promote it to active runtime contract authority and supersede baseline route
  rules above.

### Runtime Invariants That Must Be Preserved

- Enqueue correctness:
  - Never swallow queue publish failures.
  - `POST /api/jobs/enqueue` publish failures must surface as `503` with
    `error.code = "queue_unavailable"`.
  - Failed enqueue responses must not be idempotency replay cached.
- Readiness semantics:
  - `/readyz` pass/fail is based on traffic-critical dependencies only.
  - feature flags (for example `JOBS_ENABLED`) must not drive readiness
    false.
  - missing/blank `FILE_TRANSFER_BUCKET` must fail readiness.
- Worker result-update semantics:
  - `status=succeeded` updates must normalize `error` to `null`.
- Workspace packaging metadata:
  - each package/app `project.readme` path must resolve inside the same
    package/app directory.
- Rollup correctness for DynamoDB activity backend:
  - `active_users_today` increments only on first user/day marker write.
  - `distinct_event_types` increments only on first event-type/day marker
    write.
  - use conditional writes for concurrency-safe counters.
- Backend startup validation:
  - `JOBS_QUEUE_BACKEND=sqs` + `JOBS_ENABLED=true` requires
    `JOBS_SQS_QUEUE_URL`.
  - `ACTIVITY_STORE_BACKEND=dynamodb` requires `ACTIVITY_ROLLUPS_TABLE`.

## Monorepo Navigation Commands

Always run from repository root unless task scope requires otherwise.

```bash
rg --files apps packages docs
find apps packages -maxdepth 3 -type d | sort
rg -n "/api/transfers|/api/jobs|/metrics/summary|/healthz|/readyz" \
  packages docs
rg -n "nova_file_api|nova_auth_api|nova_dash_bridge" \
  apps packages docs
```

## Required Quality Gates

Always prefix commands with `source .venv/bin/activate &&`.

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

## Execution Commands by Scope

### Workspace and dependency sync

```bash
source .venv/bin/activate && uv lock
```

### Run services locally

```bash
source .venv/bin/activate && uv run uvicorn nova_file_api_service.main:app \
  --reload
source .venv/bin/activate && uv run uvicorn nova_auth_api_service.main:app \
  --reload
```

### Targeted tests

```bash
source .venv/bin/activate && uv run pytest -q packages/nova_file_api/tests
source .venv/bin/activate && uv run pytest -q packages/nova_auth_api/tests
```

## Cross-Repo Coordination (Targeted)

### dash-pca consumer alignment

Path: `~/repos/work/pca-analysis-dash/dash-pca`

Must align:

- imports reference `nova_dash_bridge` and `nova_file_api`.
- endpoint usage references `/api/transfers/*` and `/api/jobs/*`.
- async upload + job polling behavior remains contract compliant.

Verification commands:

```bash
rg -n "/api/transfers|/api/jobs|nova_dash_bridge|nova_file_api" \
  ~/repos/work/pca-analysis-dash/dash-pca
```

### Historical retirement evidence checks (read-only)

Use these to confirm active docs do not restore retired operational authority:

```bash
rg -n "container-craft" AGENTS.md README.md PRD.md docs/architecture \
  docs/plan/release | rg -v "docs/history|historical|archive|retired|ADR-0014|SPEC-0013|SPEC-0014|ADR-0001|requirements.md|RELEASE-NOTES-2026-02-12|RELEASE-VERSION-MANIFEST|AGENTS.md:"
```

## Deployment Gates

- health endpoint responds within expected time.
- structured logs include `request_id`.
- OpenAPI schema builds and docs publish pipeline runs.

## Documentation Update Rules (Mandatory)

Any behavioral or contract change must update all affected docs in the same
change:

- `README.md` operational behavior/config summary.
- `PRD.md` product-level requirements and success criteria.
- `docs/architecture/requirements.md` requirement IDs.
- relevant `docs/architecture/spec/*.md` contract docs.
- relevant `docs/architecture/adr/*.md` decision records.
- `FINAL-PLAN.md` progress and checklist state.
- `docs/plan/PLAN.md` progress and phase checklists.
- impacted `docs/plan/subplans/*.md` and `docs/plan/triggers/*.md`.
- impacted `docs/plan/release/*.md` release artifacts.
- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md` when live AWS
  gate status changes.

When review/regression fixes change runtime semantics, include:

- explicit before/after behavior statement.
- new or updated tests listed in plan/progress notes.
- source links to official docs (AWS/FastAPI/RFC) used for decisions.

<!-- opensrc:start -->

## Source Code Reference

Dependency source code is available under `opensrc/` for internal behavior
analysis beyond public interfaces.

- Source index: `opensrc/sources.json`
- Discover local paths: `opensrc list`

Fetch additional source when needed:

```bash
npx opensrc <package>
npx opensrc pypi:<package>
npx opensrc crates:<package>
npx opensrc <owner>/<repo>
```

<!-- opensrc:end -->
