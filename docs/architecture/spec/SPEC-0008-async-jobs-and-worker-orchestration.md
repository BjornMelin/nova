---
Spec: 0008
Title: Async Jobs and Worker Orchestration
Status: Active
Version: 1.2
Date: 2026-02-12
Related:
  - "[ADR-0006: SQS + ECS worker orchestration](../adr/ADR-0006-async-orchestration-sqs-ecs-worker.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
References:
  - "[Amazon SQS Developer Guide](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html)"
  - "[Amazon ECS Developer Guide](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html)"
---

## 1. API surface

Async jobs are managed through:

- `POST /api/file-transfer/jobs/enqueue`
- `GET /api/file-transfer/jobs/{job_id}`
- `POST /api/file-transfer/jobs/{job_id}/cancel`

## 2. Job state model

States:

- `pending`
- `running`
- `succeeded`
- `failed`
- `canceled`

Ownership is scope-bound. Status and cancel operations MUST enforce caller scope.

## 3. Orchestration backends

- Local/dev default: in-memory publisher simulation.
- AWS default: SQS queue publisher and ECS worker consumers.

## 4. Failure and retry model

- Enqueue should acknowledge quickly and defer work to workers.
- Queue publish failure MUST be surfaced to clients as `503` with
  `error.code = "queue_unavailable"`.
- Queue publish failure MUST NOT return success responses.
- Queue publish failure MUST mark created job records as `failed`.
- Queue publish failure SHOULD increment a publish-failure metric for operators.
- Worker retry policy SHOULD be driven by queue semantics.
- Non-retryable failures should transition to `failed` with structured error
  details.

## 5. Idempotency

`jobs/enqueue` MUST support `Idempotency-Key` replay behavior.

Failed enqueue responses (`queue_unavailable`) MUST NOT be replay-cached.

## 6. Backend selection and startup validation

- `JOBS_QUEUE_BACKEND` controls queue backend selection.
- If `JOBS_QUEUE_BACKEND=sqs` and `JOBS_ENABLED=true`, startup MUST fail when
  `JOBS_SQS_QUEUE_URL` is not configured.
- SQS publisher retry behavior SHOULD be configurable using:
  - `JOBS_SQS_RETRY_MODE`
  - `JOBS_SQS_RETRY_TOTAL_MAX_ATTEMPTS`

## 7. Traceability

- [FR-0001](../requirements.md#fr-0001-async-job-endpoints-and-orchestration)
- [FR-0004](../requirements.md#fr-0004-idempotency-for-mutation-entrypoints)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
