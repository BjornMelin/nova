# Worker Lane Operations and Failure Handling

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-06

## Scope

Operational runbook for file-transfer async worker lane backed by SQS + DLQ and
ECS/Fargate workers.

## Architecture invariants

- Source queue (`JobsQueue`) MUST define `RedrivePolicy` to `JobsDeadLetterQueue`.
- `JobsMaxReceiveCount` controls retry-to-DLQ cutoff for poison messages.
- Worker task execution MUST use packaged `nova-file-worker`.
- Worker result callbacks MUST use canonical `JOBS_API_BASE_URL` and present
  secret-backed `JOBS_WORKER_UPDATE_TOKEN`.
- Worker stack deployment MUST always provide the secret backing
  `JOBS_WORKER_UPDATE_TOKEN`, including scale-from-zero ECS service posture.
- SQS worker messages MUST be work requests only and carry `job_id`,
  `job_type`, `scope_id`, `payload`, and `created_at`.
- `transfer.process` is the canonical worker job type and completes by copying
  a scoped upload object into the export prefix.
- Worker poison messages must remain on the source queue until SQS redrive moves
  them to DLQ; the worker must not delete malformed messages immediately.
- If `JOBS_REPOSITORY_BACKEND=dynamodb`, the jobs table MUST expose
  `scope_id-created_at-index`; scoped list APIs do not use `Scan` fallback.
- Worker ECS service MUST run with queue-depth step scaling on:
  - `AWS/SQS :: ApproximateNumberOfMessagesVisible` bootstrap queue depth
    (`>= 1`) to scale from zero
  - `AWS/SQS :: ApproximateNumberOfMessagesVisible` burst queue depth
    (`>= WorkerScaleOutQueueDepthTarget`) for sustained load
  - `AWS/SQS :: ApproximateNumberOfMessagesVisible` surge queue depth
    (`>= 500`) for burst recovery
  - empty queue for sustained scale-in
- `AWS/SQS :: ApproximateAgeOfOldestMessage` remains an operator alarm only.
- Worker API result updates MUST preserve terminal-state immutability and reject
  invalid transitions with `409 conflict`.

## Queue + DLQ triage

1. Inspect queue-depth alarms and oldest-message age alarm.
2. If backlog is growing with low worker count, verify the bootstrap/burst/
   surge alarms and policy attachments.
3. If DLQ receives messages:
   - inspect payload + failure reason from job state (`failed` + `error`),
   - classify retryable vs non-retryable defects,
   - fix worker/code/config root cause before replay.
4. Re-drive from DLQ only after root-cause correction.

## Worker failure semantics

- Publish failure at enqueue path returns `503 queue_unavailable` and job state
  transitions to `failed`.
- Worker transitions allowed:
  - `pending -> pending|running|succeeded|failed|canceled`
  - `running -> running|succeeded|failed|canceled`
  - terminal states are idempotent same-state only.
- `succeeded` always clears error payload.
- SQS visibility timeout must cover worker processing plus result-callback time.

## Scaling guardrails

- Ensure `WorkerMinTaskCount <= WorkerMaxTaskCount` (validated in CI infra
  contract checks).
- `DesiredCount` controls initial ECS desired tasks at deployment time.
- `JOBS_WORKER_UPDATE_TOKEN` secret wiring is mandatory even when
  `DesiredCount=0` and `WorkerMinTaskCount=0`.
- Keep `WorkerMinTaskCount` >= 1 in environments requiring steady drain.
- Set `WorkerMaxTaskCount` to known safe account/service quotas.
- Tune `WorkerScaleOutQueueDepthTarget` from observed sustained-backlog
  throughput.
- `500` visible messages is the fixed surge threshold for aggressive scale-out.
- Tune `WorkerScaleOutQueueAgeSecondsTarget` for operator alert sensitivity.
- Avoid disabling scale-in entirely; prefer cooldown tuning.

## Recovery checklist

1. Confirm ECS service healthy and task definition current.
2. Confirm the task definition still runs `nova-file-worker`.
3. Confirm queue URL/ARN/name wiring in worker task env and IAM policy.
4. Confirm `JOBS_API_BASE_URL` targets the active canonical runtime base URL.
5. Confirm `JOBS_WORKER_UPDATE_TOKEN` resolves from the expected secret and the
   internal callback path accepts the token.
6. Confirm DLQ redrive policy still references active DLQ ARN.
7. Confirm DynamoDB jobs-table deployments include
   `scope_id-created_at-index` when scoped listing runs against DynamoDB.
8. Confirm bootstrap/burst/surge queue-depth alarms and the empty-queue
   scale-in alarm are present.
9. Confirm the queue-age alarm is present for drain visibility.
10. Reprocess failed jobs only after upstream dependency stability is verified.
