# Execution Plan: Immediate Implementation With Master Subplan Tracker

## Summary

Implement the full approved 3-repo scope (`aws-file-transfer-api`, `container-craft`, `dash-pca`) using a single master tracker file first, then execute all code/infra/docs/test tasks while continuously updating that tracker with checkboxes, notes, blockers, and evidence.

## Important Interface/Contract Changes

1. `aws-file-transfer-api` remains canonical jobs control-plane owner.
2. `container-craft` adds additive/opt-in async/file-transfer infra and worker wiring.
3. `dash-pca` consumes canonical `/api/file-transfer/jobs/*` endpoints (no divergent app-local contract).
4. All new behavior remains opt-in and backward-compatible by default.

## Step 0 (Required First Action)

1. Create new file:
   - `docs/plan/subplans/SUBPLAN-0005.md` (in `aws-file-transfer-api`)
2. Populate it with the **entire exact approved plan text** from the previous response.
3. Add execution tracking sections at the top of that same file:
   - `Status`
   - `Last Updated`
   - `Current Repo Focus`
   - `Active Checklist`
   - `Blockers/Decisions`
   - `Evidence Log`
4. From that point onward, every implementation step must update this file:
   - mark tasks `[ ] -> [x]`
   - add concise evidence notes (tests/render output/paths changed)
   - append blocker notes and decisions

## Step 1: Tracker Governance (always-on)

1. Treat `docs/plan/subplans/SUBPLAN-0005.md` as the single execution source of truth.
2. At start/end of each work chunk:
   - update current active tasks
   - update evidence log with command outputs summary
3. On context loss/compaction:
   - resume by reading this file first
   - continue from unchecked items in order

## Step 2: Container-Craft Foundation (implement first)

1. Add async/file-transfer infra stacks (queue/DLQ/tables + worker ECS stack).
2. Extend renderer/settings/template/action run-mode wiring (additive, opt-in).
3. Add env injection and IAM least-privilege wiring for API and worker.
4. Add/extend renderer unit/integration tests and render assertions.
5. Update container-craft docs/spec/ADR/PLAN artifacts.
6. Check off completed container-craft sections in `SUBPLAN-0005.md`.

## Step 3: aws-file-transfer-api Completion

1. Implement durable Dynamo job repository backend.
2. Implement worker result update endpoint(s) for status transitions.
3. Complete queue lag/worker throughput observability gaps.
4. Preserve enforced semantics:
   - `503 queue_unavailable` on publish failure
   - failed enqueue not idempotency-cached
   - readiness excludes feature flags
5. Expand tests for new repo backend + worker update contracts.
6. Update docs/spec/ADR/PLAN and mark completion in tracker.

## Step 4: dash-pca Full Integration

1. Keep direct-to-S3 integration and sync path behavior.
2. Route async path to canonical `aws-file-transfer-api` jobs endpoints.
3. Implement worker flow for large-file processing and status updates.
4. Complete export download via presigned S3 path.
5. Expand callback/service/settings tests and integration tests.
6. Update docs and check off all dash-pca sections in tracker.

## Step 5: Cross-Repo Consistency and Closure

1. Validate naming/env-contract consistency across all repos.
2. Ensure every planned item is checked off with evidence in `SUBPLAN-0005.md`.
3. Run required repo checks per repo and log summarized results in tracker.
4. Record residual risks (if any) and explicit follow-ups in tracker footer.

## Test Cases and Scenarios (Mandatory)

## 1. API correctness

1. Enqueue success returns `200` + job pending/running path.
2. SQS publish failure returns `503 queue_unavailable`.
3. Failed enqueue is not idempotency replay cached.
4. Worker result update transitions allowed states only.
5. Readiness remains true when jobs disabled but critical deps healthy.

## 2. Durability/rollups

1. Dynamo job repository create/get/update lifecycle.
2. Activity summary `distinct_event_types` increments correctly under repeated events.
3. Marker conditional writes remain concurrency-safe.

## 3. Template/IaC correctness

1. `file_transfer_async_enabled=false` => no async/worker stacks rendered.
2. `file_transfer_async_enabled=true` => async stack rendered with queue/DLQ/tables.
3. `file_transfer_worker_enabled=true` => worker stack rendered and correctly parameterized.
4. ECS IAM policies include least-privilege resource scoping for enabled features.

## 4. Dash async E2E (mocked/system integration, non-cloud)

1. Large upload metadata enqueues job.
2. Worker consumes message and posts status updates.
3. UI polling resolves to success and displays results.
4. Failure path surfaces error cleanly and keeps app stable.

## 5. Regression suite

1. Existing direct-to-S3 upload/download behavior unchanged for current users.
2. Existing non-file-transfer mode fallback works.
3. Existing auth and request-id/metrics endpoints unaffected.

## Execution Order (for implementation phase after approval)

1. `container-craft`: infra/templates/renderer/action + tests/docs (foundation first).
2. `aws-file-transfer-api`: durable repo + worker update endpoints + tests/docs.
3. `dash-pca`: consume canonical jobs API + worker + callback integrations + tests/docs.
4. Cross-repo consistency pass and final checklist closure.

Parallelization allowed:

- Docs/spec/ADR updates can run in parallel with code per repo.
- Unit tests can run per repo immediately after each phase.

## Deliverables and Definition of Done

A. `container-craft`

1. Async/worker IaC templates implemented and rendered.
2. Renderer/settings/action wiring complete.
3. Tests passing; docs/ADR/SPEC/PLAN updated.

B. `aws-file-transfer-api`

1. Durable Dynamo job repo implemented.
2. Worker result update contract implemented.
3. Existing reliability/readiness fixes preserved.
4. Tests and docs updated.

C. `dash-pca`

1. Async large-file processing integrated via canonical jobs control-plane.
2. Worker implemented with queue consume + status update callbacks.
3. UI async polling/results hydration complete.
4. Tests and docs updated.

D. Cross-repo

1. Consistent env and contract naming.
2. Complete plans/checklists updated in all repos.
3. All required local checks/tests pass in each repo.

## Assumptions and Defaults

1. Completion gate is code-complete (repo tests + render validation), not mandatory live cloud deployment.
2. Backward compatibility is additive/opt-in only.
3. `SUBPLAN-0005.md` is the persistent execution log and must be updated continuously.
4. Minimal deployment workflow complexity changes; only required run-mode additions are introduced.
5. `aws-file-transfer-api` remains canonical owner of jobs control-plane semantics.
6. Worker status update flows through API endpoints (not direct shared-table mutation by default) to centralize state semantics.

---

## Status

- Active

## Last Updated

- 2026-02-12

## Current Repo Focus

- aws-file-transfer-api

## Active Checklist

- [x] Create `SUBPLAN-0005.md` and seed full approved plan text
- [x] Implement container-craft async/file-transfer infra and wiring
- [x] Implement aws-file-transfer-api durable job backend + worker update contract
- [x] Close queue-lag and worker-throughput observability gaps in aws-file-transfer-api
- [x] Implement dash-side canonical async integration hooks + polling
- [ ] Implement app-specific worker execution path in `dash-pca` repo
- [x] Run all required checks and update evidence log

## Blockers/Decisions

- Decision: Full 3-repo scope
- Decision: Additive opt-in compatibility only
- Decision: Canonical async control plane is `aws-file-transfer-api`
- Decision: Code-complete acceptance gate (no required live deploy)
- Note: `dash-pca` app repo path was not present in current `infra-stack`
  workspace; applied async integration hooks in `aws-dash-s3-file-handler`.

## Evidence Log

- 2026-02-12: Seeded master tracker file and initial execution checklist.
- 2026-02-12: Completed `container-craft` async foundation implementation (new async/worker IaC templates, renderer wiring, action run modes, env + IAM mapping, docs/spec/ADR updates).
- 2026-02-12: `container-craft` validation passed:
  - `uv run -- ruff check .`
  - `uv run -- mypy`
  - `uv run -- pytest -q` (48 passed)
- 2026-02-12: Re-ran `container-craft` validation after cross-repo updates:
  - `uv run -- ruff check .`
  - `uv run -- mypy`
  - `uv run -- pytest -q` (48 passed)
- 2026-02-12: Completed `aws-file-transfer-api` durable job state support:
  - added DynamoDB-backed job repository (`JOBS_REPOSITORY_BACKEND=dynamodb`)
  - added worker/internal result callback endpoint (`POST /api/file-transfer/jobs/{job_id}/result`)
  - enforced legal state transitions with `409 conflict` on invalid transitions
  - preserved enqueue/reliability/readiness/distinct-event fixes
- 2026-02-12: `aws-file-transfer-api` validation passed:
  - `source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .`
  - `source .venv/bin/activate && uv run mypy`
  - `source .venv/bin/activate && uv run pytest -q` (22 passed)
- 2026-02-12: Completed authoritative research refresh using:
  - AWS docs tools (SQS SendMessage API, SQS retry/error handling, DynamoDB UpdateItem/conditional operations, SQS CloudWatch metrics)
  - Context7 (FastAPI 0.128.0 header/auth error patterns, boto3 retry config)
  - Exa deep research run `r_01kh8r35yextypwcanhh6p1acc` (completed)
- 2026-02-12: Implemented optional canonical async job hooks in
  `aws-dash-s3-file-handler`:
  - `S3FileUploader` async options
  - browser asset enqueue/poll/download-presign flow against
    `/api/file-transfer/jobs/*`
  - contract tests + docs/ADR/SPEC/traceability updates
- 2026-02-12: `aws-dash-s3-file-handler` validation passed:
  - `uv sync --group dev`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy .`
  - `uv run pytest` (44 passed)
- 2026-02-12: Closed aws-file-transfer-api worker observability gap:
  - added `jobs_queue_lag_ms` on first transition out of `pending`
  - added `jobs_worker_result_updates_total` + per-status throughput counters
  - added regression tests for queue lag and worker update metrics
- 2026-02-12: Re-ran `aws-file-transfer-api` validation after observability
  updates:
  - `source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .`
  - `source .venv/bin/activate && uv run mypy`
  - `source .venv/bin/activate && uv run pytest -q` (23 passed)
- 2026-02-12: Final validation rerun after docs/ADR/spec version alignment:
  - `source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .`
  - `source .venv/bin/activate && uv run mypy`
  - `source .venv/bin/activate && uv run pytest -q` (23 passed)
