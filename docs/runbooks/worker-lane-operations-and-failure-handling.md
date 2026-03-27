# Worker Lane Operations and Failure Handling

> Legacy environment note: this runbook applies only to retained ECS/SQS worker
> deployments. The canonical export runtime now uses Step Functions task
> handlers in `packages/nova_workflows/`.

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-11
Authority: ADR-0023, SPEC-0000, SPEC-0016, requirements.md

## Scope

Operational runbook for file-transfer async worker lane backed by SQS + DLQ and
ECS/Fargate workers.

## Architecture invariants

- Source queue (`JobsQueue`) MUST define `RedrivePolicy` to `JobsDeadLetterQueue`.
- `JobsMaxReceiveCount` controls retry-to-DLQ cutoff for poison messages.
- Worker tasks MUST run the installed `nova-file-worker` command and use
  canonical `JOBS_*` runtime inputs.
- Worker ECS service MUST run with autoscaling target tracking on:
  - `AWS/SQS :: ApproximateNumberOfMessagesVisible`
  - `AWS/SQS :: ApproximateAgeOfOldestMessage`
- Worker result updates MUST preserve terminal-state immutability and reject
  invalid transitions with `409 conflict`.
- Long-running worker operations MUST extend SQS visibility before half of the
  configured timeout elapses.

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
2. Confirm worker task definition command is `nova-file-worker`.
3. Confirm canonical worker env wiring:
   - `JOBS_ENABLED=true`
   - `JOBS_RUNTIME_MODE=worker`
   - `JOBS_QUEUE_BACKEND=sqs`
   - `JOBS_SQS_QUEUE_URL`
   - `JOBS_REPOSITORY_BACKEND=dynamodb`
   - `JOBS_DYNAMODB_TABLE`
   - `ACTIVITY_STORE_BACKEND=dynamodb`
   - `ACTIVITY_ROLLUPS_TABLE`
   - `JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS`
   - `FILE_TRANSFER_BUCKET`
   - `FILE_TRANSFER_UPLOAD_PREFIX`
   - `FILE_TRANSFER_EXPORT_PREFIX`
   - `FILE_TRANSFER_TMP_PREFIX`
4. Confirm queue and DynamoDB table wiring in worker task env and IAM policy.
5. Confirm visibility-extension warnings are absent or understood
   (`jobs_worker_visibility_extension_failed`).
6. Confirm DLQ redrive policy still references active DLQ ARN.
7. Confirm both queue-depth and queue-age scaling policies are present.
8. Reprocess failed jobs only after upstream dependency stability is verified.
