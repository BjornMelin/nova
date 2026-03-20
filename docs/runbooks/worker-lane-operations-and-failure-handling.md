# Worker Lane Operations and Failure Handling

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
- `JOBS_WORKER_UPDATE_TOKEN` MUST be injected through ECS `Secrets` sourced
  from operator input `JOBS_WORKER_UPDATE_TOKEN_SECRET_ARN`.
- Worker ECS service MUST run with autoscaling target tracking on:
  - `AWS/SQS :: ApproximateNumberOfMessagesVisible`
  - `AWS/SQS :: ApproximateAgeOfOldestMessage`
- Worker API result updates MUST preserve terminal-state immutability and reject
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
- Keep the worker token secret current and redeploy ECS tasks after secret
  rotation; ECS secret injection is task-start scoped.

## Recovery checklist

1. Confirm ECS service healthy and task definition current.
2. Confirm worker task definition command is `nova-file-worker`.
3. Confirm canonical worker env wiring only:
   - `JOBS_ENABLED=true`
   - `JOBS_RUNTIME_MODE=worker`
   - `JOBS_QUEUE_BACKEND=sqs`
   - `JOBS_SQS_QUEUE_URL`
   - `JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS`
   - `JOBS_API_BASE_URL`
   - `FILE_TRANSFER_BUCKET`
   - `FILE_TRANSFER_UPLOAD_PREFIX`
   - `FILE_TRANSFER_EXPORT_PREFIX`
   - `FILE_TRANSFER_TMP_PREFIX`
4. Confirm `JOBS_WORKER_UPDATE_TOKEN` is injected through ECS `Secrets` from
   `JOBS_WORKER_UPDATE_TOKEN_SECRET_ARN`.
5. Confirm queue URL/ARN/name wiring in worker task env and IAM policy.
6. Confirm visibility-extension warnings are absent or understood
   (`jobs_worker_visibility_extension_failed`).
7. Confirm DLQ redrive policy still references active DLQ ARN.
8. Confirm both queue-depth and queue-age scaling policies are present.
9. Reprocess failed jobs only after upstream dependency stability is verified.
