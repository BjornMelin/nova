---
Spec: 0008
Title: Async Jobs and Worker Orchestration
Status: Active
Version: 1.11
Date: 2026-03-06
Related:
  - "[ADR-0006: SQS + ECS worker orchestration](../adr/ADR-0006-async-orchestration-sqs-ecs-worker.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0001: Security model](./SPEC-0001-security-model.md)"
  - "[SPEC-0009: Caching and idempotency](./SPEC-0009-caching-and-idempotency.md)"
References:
  - "[Amazon SQS Developer Guide](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html)"
  - "[Amazon ECS Developer Guide](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html)"
---

## 1. API surface

Async jobs are managed through:

- `POST /v1/jobs`
- `GET /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `POST /v1/jobs/{job_id}/cancel`
- `POST /v1/jobs/{job_id}/retry`
- `GET /v1/jobs/{job_id}/events`
- `POST /v1/internal/jobs/{job_id}/result` (worker/internal update path)

For same-origin deployments, browser polling clients calling body-less
job-scope routes (`GET /v1/jobs/{job_id}`, `GET /v1/jobs/{job_id}/events`,
`POST /v1/jobs/{job_id}/cancel`, `POST /v1/jobs/{job_id}/retry`) MUST send
caller scope context via trusted header (`X-Session-Id` or `X-Scope-Id`).
When `X-Session-Id` and `X-Scope-Id` are both present, `X-Session-Id` is the
canonical scope input. If `X-Session-Id` and body `session_id` are both present
and differ, request validation MUST fail with `422`
(`error.message = "conflicting session scope"`). If `X-Session-Id` is absent
and `X-Scope-Id` plus body `session_id` are both present and differ,
authentication MUST fail with `401`
(`error.message = "conflicting session scope"`).

### 1.1 Endpoint payload contracts

Canonical request/response schemas are owned by SPEC-0000 and the OpenAPI
contract generated from runtime implementation. For async additions:

- `POST /v1/jobs/{job_id}/retry`
  - Request body: empty object (`{}`).
  - Response: `JobStatusResponse` for the updated job record.
  - Errors: shared error envelope with `401/403/404/409/500` semantics aligned
    with SPEC-0000.
- `GET /v1/jobs/{job_id}/events`
  - Request body: none; optional query params `cursor` and `limit`.
  - Response: `JobEventsResponse` containing `events[]`, `next_cursor`, and
    `has_more`.
  - Event item shape: `JobEvent` with `event_type`, `message`, `details`,
    `created_at`.
  - Errors: shared error envelope with `401/403/404/500` semantics aligned with
    SPEC-0000.

## 2. Job state model

States:

- `pending`
- `running`
- `succeeded`
- `failed`
- `canceled`

Ownership is scope-bound. Status and cancel operations MUST enforce caller scope.

Worker status updates MUST enforce legal transitions:

- `pending -> pending|running|succeeded|failed|canceled`
  - `pending -> succeeded` is allowed for atomic worker completion across
    backends.
  - in-memory `process_immediately` simulation currently transitions through
    `pending -> running -> succeeded`.
- `running -> running|succeeded|failed|canceled`
- terminal states (`succeeded|failed|canceled`) allow same-state idempotent
  updates only.
- `status = succeeded` updates MUST clear `error` to `null`.

Invalid transitions MUST fail with `409` (`error.code = "conflict"`).

## 3. Orchestration backends

- Local/dev default: in-memory publisher simulation.
- `MemoryJobPublisher(process_immediately=False)` MUST preserve `pending`
  state after enqueue (no auto-complete simulation).
- AWS default: SQS queue publisher and ECS worker consumers.
- Worker process execution MUST use the packaged command `nova-file-worker`
  (direct `src/worker.py` invocation is non-canonical).

## 4. Failure and retry model

- Enqueue SHOULD acknowledge quickly and defer work to workers.
- On queue publish failure:
  - MUST return `503` with `error.code = "queue_unavailable"`.
  - MUST NOT return success responses.
  - MUST mark created job records as `failed`.
  - SHOULD increment a publish-failure metric for operators.
- Worker retry policy SHOULD be driven by queue semantics.
- Malformed or unparseable worker messages MUST remain unacked so queue retry
  and DLQ policy handle poison messages deterministically.
- Retryable worker result-update failures MUST also leave the source message
  unacked so SQS retry can replay the completion callback path.
- Queue topology MUST include a dedicated dead-letter queue (DLQ) and source
  queue `RedrivePolicy.maxReceiveCount` so terminal poison messages leave the
  hot queue deterministically.
- Queue visibility timeout MUST be sized to cover worker processing and result
  callback time, not just receive-loop latency.
- Non-retryable failures SHOULD transition to `failed` with structured error
  details.
- First worker transition from `pending` MUST record queue lag metric
  (`jobs_queue_lag_ms`).
- Worker result-update calls MUST increment throughput counters
  (`jobs_worker_result_updates_total` and per-status counters).
- Worker ECS desired-count autoscaling MUST be target-tracked from queue depth
  and queue age metrics (`ApproximateNumberOfMessagesVisible`,
  `ApproximateAgeOfOldestMessage`) to prevent backlog growth under burst load.

## 5. Idempotency

`POST /v1/jobs` MUST support `Idempotency-Key` replay behavior.

Failed enqueue responses (`queue_unavailable`) MUST NOT be replay-cached.
When distributed idempotency is configured, claim-store outages MUST fail
enqueue with `503` (`error.code = "idempotency_unavailable"`).

## 6. Backend selection and startup validation

- `JOBS_RUNTIME_MODE` controls runtime role selection (`api|worker`).
- `JOBS_QUEUE_BACKEND` controls queue backend selection.
- `JOBS_REPOSITORY_BACKEND` controls job state persistence backend.
- If `JOBS_QUEUE_BACKEND=sqs` and `JOBS_ENABLED=true`, startup MUST fail when
  `JOBS_SQS_QUEUE_URL` is not configured.
- If `JOBS_REPOSITORY_BACKEND=dynamodb`, startup MUST fail when
  `JOBS_DYNAMODB_TABLE` is not configured.
- If `JOBS_REPOSITORY_BACKEND=dynamodb`, the jobs table MUST expose the GSI
  `scope_id-created_at-index` for scope-ordered listing; scoped list calls must
  not fall back to `Scan`.
- Worker runtime (`JOBS_RUNTIME_MODE=worker`) MUST enforce canonical
  `JOBS_*` contract at startup:
  - `JOBS_ENABLED=true`
  - `JOBS_QUEUE_BACKEND=sqs`
  - `JOBS_SQS_QUEUE_URL` configured
  - `JOBS_API_BASE_URL` configured
  - `JOBS_WORKER_UPDATE_TOKEN` configured and passed as `X-Worker-Token`
- SQS publisher retry behavior SHOULD be configurable using:
  - `JOBS_SQS_RETRY_MODE`
  - `JOBS_SQS_RETRY_TOTAL_MAX_ATTEMPTS`

## 7. Traceability

- [FR-0001](../requirements.md#fr-0001-async-job-endpoints-and-orchestration)
- [FR-0004](../requirements.md#fr-0004-idempotency-for-mutation-entrypoints)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)

## Changelog

- 2026-03-06 (v1.11): Documented DynamoDB jobs-table GSI requirement and
  retryable worker result-update retry semantics.
- 2026-03-05 (v1.9): Added canonical worker runtime `JOBS_*` startup contract
  requirements for `JOBS_RUNTIME_MODE=worker` and documented packaged worker
  executable `nova-file-worker`.
- 2026-03-05 (v1.10): Documented poison-message retry/DLQ handling, visibility
  timeout sizing, and `idempotency_unavailable` enqueue behavior for
  distributed idempotency mode.
- 2026-03-03 (v1.8): Canonicalized job route documentation to `/v1/*`, added
  `/v1/jobs/{job_id}/retry` and `/v1/jobs/{job_id}/events` endpoint contract
  details, and updated internal worker callback route to
  `/v1/internal/jobs/{job_id}/result`.
- 2026-03-02 (v1.7): Added worker-lane DLQ redrive and autoscaling invariants
  for async job workers.
