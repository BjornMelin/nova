---
Spec: 0008
Title: Async Jobs and Worker Orchestration
Status: Active
Version: 1.7
Date: 2026-02-23
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

Transition note (2026-03-02): This specification remains active for baseline
`/api/jobs/*` behavior. Planned `/v1/jobs*` target-state capability endpoints
are tracked in `SPEC-0015` and remain implementation-pending.

Async jobs are managed through:

- `POST /api/jobs/enqueue`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/cancel`
- `POST /api/jobs/{job_id}/result` (worker/internal update path)

For same-origin deployments, browser polling clients calling body-less
job-scope routes (`GET /api/jobs/{job_id}`, `POST /api/jobs/{job_id}/cancel`)
MUST send caller scope context via trusted header (`X-Session-Id` or
`X-Scope-Id`).
When `X-Session-Id` and `X-Scope-Id` are both present, `X-Session-Id` is the
canonical scope input. If `X-Session-Id` and body `session_id` are both present
and differ, request validation MUST fail with `422`
(`error.message = "conflicting session scope"`). If `X-Session-Id` is absent
and `X-Scope-Id` plus body `session_id` are both present and differ,
authentication MUST fail with `401`
(`error.message = "conflicting session scope"`).

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

`jobs/enqueue` MUST support `Idempotency-Key` replay behavior.

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

- 2026-03-02 (v1.7): Added worker-lane invariants for SQS DLQ redrive policy and ECS queue depth/age autoscaling authority.
