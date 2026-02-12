# AGENTS.md (aws-file-platform runtime)

This repository is the canonical runtime monorepo for file-transfer and
auth API services. Infrastructure and IaC remain in
`~/repos/work/infra-stack/container-craft`, and consumer migration work
includes `~/repos/work/pca-analysis-dash/dash-pca`.

## Runtime Topology

- `apps/aws_file_api_service/`: ASGI wrapper for file API runtime.
- `apps/aws_auth_api_service/`: ASGI wrapper for auth API runtime.
- `packages/aws_file_api/`: transfer + async jobs control-plane package.
- `packages/aws_auth_api/`: token verify/introspect service package.
- `packages/aws_dash_bridge/`: Dash/Flask/FastAPI bridge adapters.
- `packages/contracts/`: OpenAPI and shared contract artifacts.
- `docs/architecture/`: requirements, ADRs, and SPECs.
- `docs/plan/`: execution plans, subplans, and triggers.

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

- Work from `FINAL-PLAN.md` as the canonical execution source.
- Keep `docs/plan/PLAN.md` synchronized with current implementation state.
- Treat OpenAPI as the contract and update SPEC/ADR docs first for
  contract-level changes.
- Keep dependencies lean and maintained.
- Never log presigned URLs, JWTs, or signed query values.
- Never run synchronous JWT verification directly in async route/dependency
  code; use a threadpool boundary.

### Hard-Cutover Contract Rules (Blocking)

- Use only:
  - `/api/transfers/*`
  - `/api/jobs/*`
  - `/metrics/summary`
- Do not introduce legacy names or paths:
  - `/api/file-transfer/*`
  - `aws_file_transfer_api`
  - `aws_dash_s3_file_handler`
- Do not add compatibility alias routes or namespace shims.
- Fail reviews when legacy patterns are introduced.

Required verification command:

```bash
source .venv/bin/activate && \
rg -n "/api/file-transfer|aws_file_transfer_api|aws_dash_s3_file_handler" .
```

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
rg -n "/api/transfers|/api/jobs|/metrics/summary" \
  packages docs
rg -n "aws_file_api|aws_auth_api|aws_dash_bridge" \
  apps packages docs
```

## Required Quality Gates

Always prefix commands with `source .venv/bin/activate &&`.

```bash
source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .
source .venv/bin/activate && uv run mypy
source .venv/bin/activate && uv run pytest -q
```

## Execution Commands by Scope

### Workspace and dependency sync

```bash
source .venv/bin/activate && uv lock
```

### Run services locally

```bash
source .venv/bin/activate && uv run uvicorn aws_file_api_service.main:app \
  --reload
source .venv/bin/activate && uv run uvicorn aws_auth_api_service.main:app \
  --reload
```

### Targeted tests

```bash
source .venv/bin/activate && uv run pytest -q packages/aws_file_api/tests
source .venv/bin/activate && uv run pytest -q packages/aws_auth_api/tests
```

## Cross-Repo Coordination (Required Before Finalizing)

### container-craft alignment

Path: `~/repos/work/infra-stack/container-craft`

Must align:

- ALB routing for `/api/transfers/*` and `/api/jobs/*`.
- health-check tuning for sidecar services.
- env contract for SQS/Redis/DynamoDB settings.
- IAM least privilege for S3/KMS/SQS/DynamoDB/Redis.

Verification commands:

```bash
rg -n "/api/transfers|/api/jobs|FILE_TRANSFER_|JOBS_SQS_RETRY_" \
  ~/repos/work/infra-stack/container-craft
```

### dash-pca alignment

Path: `~/repos/work/pca-analysis-dash/dash-pca`

Must align:

- imports reference `aws_dash_bridge` and `aws_file_api`.
- endpoint usage references `/api/transfers/*` and `/api/jobs/*`.
- async upload + job polling behavior remains contract compliant.

Verification commands:

```bash
rg -n "/api/transfers|/api/jobs|aws_dash_bridge|aws_file_api" \
  ~/repos/work/pca-analysis-dash/dash-pca
```

Before closing work, include cross-repo evidence in summary output.

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
