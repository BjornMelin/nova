---
Spec: 0008
Title: Async Jobs and Worker Orchestration
Status: Active
Version: 1.9
Date: 2026-03-11
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: v1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
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
  - Response: `JobEventsResponse` containing `job_id`, `next_cursor`, and
    `events[]`.
  - Event item shape: `JobEvent` with `event_id`, `job_id`, `status`,
    `timestamp`, and optional `data` and `event_type` fields.
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

## 4. Failure and retry model

- Enqueue SHOULD acknowledge quickly and defer work to workers.
- On queue publish failure:
  - MUST return `503` with `error.code = "queue_unavailable"`.
  - MUST NOT return success responses.
  - MUST mark created job records as `failed`.
  - SHOULD increment a publish-failure metric for operators.
- Worker retry policy SHOULD be driven by queue semantics.
- Queue topology MUST include a dedicated dead-letter queue (DLQ) and source
  queue `RedrivePolicy.maxReceiveCount` so terminal poison messages leave the
  hot queue deterministically.
- Long-running worker operations MUST extend message visibility before half of
  the configured timeout elapses instead of relying only on static
  `VisibilityTimeout` sizing.
- Long-running worker operations MUST NOT rely on visibility extensions beyond
  the SQS 12-hour (43,200 second) ceiling from the original receive; work that
  may exceed that cap MUST checkpoint, split, re-enqueue, or fail before the
  window is exhausted.
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

## 6. Backend selection and startup validation

- `JOBS_QUEUE_BACKEND` controls queue backend selection.
- `JOBS_REPOSITORY_BACKEND` controls job state persistence backend.
- If `JOBS_QUEUE_BACKEND=sqs` and `JOBS_ENABLED=true`, startup MUST fail when
  `JOBS_SQS_QUEUE_URL` is not configured.
- If `JOBS_REPOSITORY_BACKEND=dynamodb`, startup MUST fail when
  `JOBS_DYNAMODB_TABLE` is not configured.
- SQS publisher retry behavior SHOULD be configurable using:
  - `JOBS_SQS_RETRY_MODE`
  - `JOBS_SQS_RETRY_TOTAL_MAX_ATTEMPTS`

Worker status callbacks MUST validate `X-Worker-Token` when
`JOBS_WORKER_UPDATE_TOKEN` is configured, per SPEC-0001 §6.

## 7. Traceability

- [FR-0001](../requirements.md#fr-0001-async-job-endpoints-and-orchestration)
- [FR-0004](../requirements.md#fr-0004-idempotency-for-mutation-entrypoints)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)

## Changelog

- 2026-03-11 (v1.9): Added heartbeat-based SQS visibility-extension
  requirement for long-running worker operations.
- 2026-03-03 (v1.8): Canonicalized job route documentation to `/v1/*`, added
  `/v1/jobs/{job_id}/retry` and `/v1/jobs/{job_id}/events` endpoint contract
  details, and updated internal worker callback route to
  `/v1/internal/jobs/{job_id}/result`.
- 2026-03-02 (v1.7): Added worker-lane DLQ redrive and autoscaling invariants
  for async job workers.
