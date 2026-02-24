# PRD: Deployable File Transfer API (FastAPI) for container-craft apps

**Date:** 2026-02-12
**Status:** Active release track

## 1. Problem

We need a reusable, production-grade API service that provides a stable file
transfer control-plane so browser clients can upload/download from S3
efficiently without proxying large payloads through web application containers.

The service must be usable by:

- Dash apps (Python)
- Shiny apps (R)
- Next.js apps (TypeScript)

## 2. Product Goals

1. Implement and maintain the split endpoint contract:
   `/api/transfers/*` and `/api/jobs/*`.
2. Support uploads from small files to very large objects (multi-GB), including
   multipart workflows with strict S3 constraints.
3. Support Transfer Acceleration when enabled in infra and runtime settings.
4. Provide strong security boundaries:
   - authenticated access (same-origin or JWT modes)
   - scoped key ownership enforcement
   - least-privilege IAM integration
5. Provide high-quality API contract artifacts:
   - OpenAPI 3.1 as source-of-truth contract
   - docs and SDK-generation-ready output
6. Provide reliable async orchestration with explicit queue-failure semantics.

## 3. Functional Requirements Summary

- File transfer endpoints:
  - initiate/sign-parts/complete/abort upload
  - presign download
- Async jobs endpoints:
  - enqueue/status/cancel
  - worker/internal result update callback (`/jobs/{job_id}/result`)
- Operational endpoints:
  - `/healthz`
  - `/readyz`
  - `/metrics/summary`
- Idempotency on protected mutation entrypoints:
  - `uploads/initiate`
  - `jobs/enqueue`

### 3.1 Reliability and correctness requirements

- Queue publish failures during `jobs/enqueue` must be client-visible:
  - response status `503`
  - `error.code = "queue_unavailable"`
- Enqueue publish failures must not be reported as successful enqueue.
- Failed enqueue attempts must not be idempotency replay cached.
- Idempotency handling must use explicit claim/commit/discard lifecycle for
  mutation safety and retry correctness.
- JWT verification cache TTL must not exceed token `exp` and configured max TTL
  bounds.
- Worker status updates must enforce legal job state transitions and reject
  invalid transitions with `409 conflict`.
- Worker `succeeded` updates must always clear job `error` state.
- Worker processing must emit queue lag and throughput metrics:
  - `jobs_queue_lag_ms` on first transition out of `pending`
  - `jobs_worker_result_updates_total` and per-status update counters
- Same-origin browser polling for body-less async job routes must propagate
  caller scope via trusted headers (`X-Session-Id` or `X-Scope-Id`).
- Same-origin scope resolution must prioritize `X-Session-Id` over body
  `session_id` and `X-Scope-Id`; conflicting `X-Session-Id` and body
  `session_id` values must fail closed with `401`.
- In-memory queue mode must respect `process_immediately`; disabled mode must
  keep jobs in `pending` after enqueue.
- CloudWatch EMF metric logs must keep `_aws` and metric fields at the top
  level of the structured log event (not JSON-string nested).
- Readiness must reflect critical traffic-serving dependencies only.
- Feature flags (for example `JOBS_ENABLED`) must not flip readiness to false.
- Missing/blank `FILE_TRANSFER_BUCKET` must keep readiness false.
- DynamoDB activity rollups must correctly maintain:
  - `events_total`
  - `active_users_today`
  - `distinct_event_types`

## 4. Non-goals (Initial Release)

- No byte-streaming data-plane API through FastAPI.
- No workflow-engine adoption (Step Functions/Lambda orchestration) by default.
- No heavy compute pipelines bundled into this runtime.
- No broad backwards-compatibility shim layers beyond approved bridge scope.

## 5. Primary Users

- Frontend code in Dash/Shiny/Next.js that needs signed operations.
- Platform engineers maintaining container-craft deployed stacks.
- Runtime engineers operating queue/cache/metrics behavior in AWS.

## 6. Success Metrics

- Upload/download control-plane flows work end-to-end in dev and prod.
- Enqueue failure modes are accurate and observable (`503 queue_unavailable`).
- Readiness behavior matches deployment intent for optional feature toggles.
- Rollup metrics for `distinct_event_types` and `active_users_today` are
  accurate under repeated events.
- Queue lag and worker result-update throughput metrics are visible through
  metrics summaries/dashboards.
- OpenAPI schema remains stable and published through CI/CD.
- Docs and architecture artifacts stay synchronized with implementation.

## 7. Release and Quality Gates

Required quality gates:

- `source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .`
- `source .venv/bin/activate && uv run mypy`
- `source .venv/bin/activate && uv run pytest -q`

Deployment gates:

- health endpoint responds within expected time
- readiness reflects true dependency health and ignores feature toggles
- structured logs include `request_id`
- OpenAPI schema and docs pipeline are green
