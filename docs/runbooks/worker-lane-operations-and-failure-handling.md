# Worker Lane Operations and Failure Handling

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-05

## Scope

Operational runbook for file-transfer async worker lane backed by SQS + DLQ and
ECS/Fargate workers.

## Architecture invariants

- Source queue (`JobsQueue`) MUST define `RedrivePolicy` to `JobsDeadLetterQueue`.
- `JobsMaxReceiveCount` controls retry-to-DLQ cutoff for poison messages.
- Worker task execution MUST use packaged `nova-file-worker`.
- Worker result callbacks MUST use canonical `JOBS_API_BASE_URL` and present
  secret-backed `JOBS_WORKER_UPDATE_TOKEN`.
- Worker poison messages must remain on the source queue until SQS redrive moves
  them to DLQ; the worker must not delete malformed messages immediately.
- If `JOBS_REPOSITORY_BACKEND=dynamodb`, the jobs table MUST expose
  `scope_id-created_at-index`; scoped list APIs do not use `Scan` fallback.
- Worker ECS service MUST run with autoscaling target tracking on:
  - `AWS/SQS :: ApproximateNumberOfMessagesVisible`
  - `AWS/SQS :: ApproximateAgeOfOldestMessage`
- Worker API result updates MUST preserve terminal-state immutability and reject
  invalid transitions with `409 conflict`.

## Queue + DLQ triage

1. Inspect queue backlog depth and oldest-message age alarms.
2. If backlog is growing with low worker count, verify autoscaling target and
   policy attachment.
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
- Keep `WorkerMinTaskCount` >= 1 in environments requiring steady drain.
- Set `WorkerMaxTaskCount` to known safe account/service quotas.
- Tune `WorkerScaleOutQueueDepthTarget` and
  `WorkerScaleOutQueueAgeSecondsTarget` from observed processing throughput.
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
8. Confirm both queue-depth and queue-age scaling policies are present.
9. Reprocess failed jobs only after upstream dependency stability is verified.
