# SUBPLAN-0005

- Branch name: `feat/subplan-0005-cross-repo-release-tracker`

Transition note (2026-03-02): This tracker remains baseline historical
evidence. It does not define active target-state implementation steps for the
planned `/v1/*` cutover.

## Cross-Repo Release Tracker

Order: 5 of 5
Parent plan: `FINAL-PLAN.md`
Depends on: `SUBPLAN-0001`, `SUBPLAN-0002`, `SUBPLAN-0003`, `SUBPLAN-0004`

## Persona

Release Integration Architect (runtime + infra + client cutover governance)

## Status

- Active
- Last updated: 2026-02-23

## Objective

Track and verify final delivery across:

- `nova` runtime monorepo (this repo)
- `~/repos/work/infra-stack/container-craft`
- `~/repos/work/pca-analysis-dash/dash-pca`

## Master Checklist

### A. Runtime Monorepo Completion

- [x] Monorepo scaffold and package rename cutover (`nova_file_api`,
  `nova_auth_api`, `nova_dash_bridge`)
- [x] Route cutover to `/api/transfers/*` and `/api/jobs/*`
- [x] Auth hardening and RFC6750 behavior regression coverage
- [x] Async jobs/idempotency/cache/observability regression coverage
- [x] OpenAPI route-regression tests added for split-route contract
- [x] Bridge runtime delegation moved into `nova_file_api` core transfer service
- [x] Generated OpenAPI client smoke test added and passing
- [x] Workspace package/app metadata and isolated build behavior validated

### B. container-craft Alignment

- [x] Async jobs/worker wiring and retry env contract validated in renderer
- [x] Route and contract docs updated to `/api/transfers/*` + `/api/jobs/*`
- [x] Retry env contract explicitly documented:
  - `JOBS_SQS_RETRY_MODE`
  - `JOBS_SQS_RETRY_TOTAL_MAX_ATTEMPTS`
- [ ] Non-prod ALB rule + health-check behavior validated in live AWS
  deployment

### C. dash-pca Mandatory Migration

- [x] Import migration to `nova_dash_bridge` complete
- [x] Route migration to `/api/transfers/*` + `/api/jobs/*` complete
- [x] PCA policy enforcement retained (200 MB, `.csv`/`.xlsx`)
- [x] Async uploader job enqueue/poll flow wired in browser uploader
- [x] Async config aliases added to app settings (`FILE_TRANSFER_ASYNC_*`)
- [x] Callback coverage added for large-upload async status behavior

### D. Cross-Repo Verification and Closure

- [x] Quality gates passed in all three repos
- [ ] Live end-to-end non-prod smoke (browser upload -> enqueue -> worker
  result -> download)
- [ ] Dashboards/alarms synthetic-failure validation in AWS
- [x] Finalize active documentation cleanup for post-cutover steady state
- [x] Publish final release notes + hard-cutover checklist
- [x] Publish operator runbook for external live validation gates

## Evidence Log

- 2026-02-12: Runtime monorepo gates passed:
  - `source .venv/bin/activate && uv run ruff check . --fix`
  - `source .venv/bin/activate && uv run ruff format .`
  - `source .venv/bin/activate && uv run mypy`
  - `source .venv/bin/activate && uv run pytest -q`
- 2026-02-12: Runtime gate rerun after regression test expansion:
  - `source .venv/bin/activate && uv run ruff check . --fix`
  - `source .venv/bin/activate && uv run ruff format .`
  - `source .venv/bin/activate && uv run mypy`
  - `source .venv/bin/activate && uv run pytest -q`
    (`45` passed)
- 2026-02-12: Runtime gate rerun after bridge delegation and generated-client
  smoke implementation:
  - `source .venv/bin/activate && uv run ruff check . --fix`
  - `source .venv/bin/activate && uv run ruff format .`
  - `source .venv/bin/activate && uv run mypy`
  - `source .venv/bin/activate && uv run pytest -q`
    (`46` passed)
- 2026-02-12: `container-craft` gates passed:
  - `uv run -- ruff check .`
  - `uv run -- mypy`
  - `uv run -- pytest -q` (48 passed)
- 2026-02-12: `dash-pca` gates passed:
  - `source .venv/bin/activate && uv run ruff check . --fix`
  - `source .venv/bin/activate && uv run ruff format .`
  - `source .venv/bin/activate && uv run pyright`
  - `source .venv/bin/activate && uv run pytest -q`
    (353 passed, 1 skipped)
- 2026-02-12: Requirements traceability check passed:
  - links checked: `60`
  - docs files scanned: `17`
  - missing anchors: `0`
- 2026-02-12: Added queue retry/pressure validation coverage for
  `SqsJobPublisher`:
  - retry mode + attempt configuration assertions
  - publish error mapping for `ClientError` and `BotoCoreError`
- 2026-02-12: Published release closure artifacts:
  - `docs/plan/release/HARD-CUTOVER-CHECKLIST.md`
  - `docs/plan/release/RELEASE-VERSION-MANIFEST.md`
- 2026-02-12: Runtime quality gates rerun after plan/doc synchronization:
  - `source .venv/bin/activate && uv run ruff check . --fix`
  - `source .venv/bin/activate && uv run ruff format .`
  - `source .venv/bin/activate && uv run mypy`
  - `source .venv/bin/activate && uv run pytest -q`
    (`49` passed)
- 2026-02-12: Generated-client smoke gate rerun:
  - `source .venv/bin/activate && uv run pytest -q`
    `packages/nova_file_api/tests/test_generated_client_smoke.py`
    (`1` passed)
- 2026-02-12: Added external live gate operator runbook:
  - `docs/runbooks/release/nonprod-live-validation-runbook.md`
- 2026-02-23: Packaging/job/readiness remediation verification:
  - `source .venv/bin/activate && uv run pytest -q`
    `packages/nova_file_api/tests/test_jobs.py`
    `packages/nova_file_api/tests/test_app_health.py` (`25` passed)
  - `source .venv/bin/activate && uv run pytest -q` (`81` passed)
  - `source .venv/bin/activate && uv run pytest -q`
    `packages/nova_file_api/tests/test_generated_client_smoke.py`
    (`1` passed)
  - workspace build verification:
    `uv build` passed for:
    `packages/nova_file_api`,
    `packages/nova_auth_api`,
    `packages/nova_dash_bridge`,
    `packages/contracts`.

## Open Risks

- Live AWS validation steps remain pending for ALB health behavior,
  dashboards/alarms, and full non-prod cross-repo smoke. Execute:
  `docs/runbooks/release/nonprod-live-validation-runbook.md`.
