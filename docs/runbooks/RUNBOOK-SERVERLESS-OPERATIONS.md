# Runbook — canonical serverless operations

> **Implementation state:** Active operational runbook for the canonical serverless baseline.

## Core runtime

- API Gateway REST API (regional) behind one canonical custom domain
- Lambda (FastAPI via the repo-owned Lambda entrypoint, Mangum-backed, zip-packaged API runtime)
- Step Functions Standard
- DynamoDB
- S3
- AWS WAF attached to the API stage
- CloudWatch / X-Ray / OpenTelemetry-compatible telemetry

## Public ingress rules

- The custom domain is the only intended public base URL for the runtime.
- The default `execute-api` endpoint is disabled and is not an operator-facing
  invoke path.
- CloudFront is not part of the API ingress path.
- The WAF attaches directly to the Regional REST API stage.
- The WAF baseline includes AWS managed IP-reputation, common-rule, and
  known-bad-input rule groups, plus explicit rate-based blocks.
- The default rate ceilings are `2000` requests per IP over 5 minutes for all
  paths and `500` requests per IP over 5 minutes for `/v1/exports` and
  `/v1/transfers/uploads`.

## Health model

- API health is control-plane readiness only.
- Export processing health is measured via Step Functions success/failure metrics and backlog alarms.
- DynamoDB throttling, Lambda errors, and Step Functions failure rates are first-class alarms.
- Runtime alarms publish to the exported `NovaAlarmTopicArn` SNS topic.
- API access logs and WAF logs are also exported via
  `NovaApiAccessLogGroupName` and `NovaWafLogGroupName` for post-deploy
  validation and incident response.

## Primary alarms

- API 5xx rate
- API Lambda throttles
- API p95/p99 latency
- workflow-task Lambda throttles
- Lambda error rate / duration
- Step Functions failed executions
- Step Functions timed-out executions
- DynamoDB throttles
- S3 transfer failures
- DLQ depth if used on event fan-out edges

## Operational defaults

- arm64 for Lambda unless blocked
- reserved concurrency for blast-radius control in production and in
  standard-quota non-prod accounts
- production deploys fail closed if reserved concurrency cannot be applied
- non-prod deploys with reduced Lambda regional quotas may intentionally omit
  reservations and rely on the account concurrency cap plus ingress throttles
- API Lambda reserved concurrency defaults when enabled: `5` outside prod, `25`
  in prod
- workflow task Lambda reserved concurrency defaults when enabled: `2` outside
  prod, `10` in prod
- post-deploy validation treats reserved concurrency as deployed truth and
  fails if the live API/workflow Lambdas drift from those defaults
- provisioned concurrency only after measuring need
- API Gateway stage access/execution logging enabled for ingress diagnostics
- API access logs are emitted to
  `/aws/apigateway/nova-rest-api-access-{stage}` with 90-day retention
- WAF logs are emitted to `aws-waf-logs-nova-rest-api-{stage}` with 90-day
  retention, redact the `Authorization` and `Cookie` headers, and keep only
  `BLOCK` / `COUNT` actions
- S3 aborts incomplete multipart uploads after 7 days and expires transient
  `tmp/` objects after 3 days; exported artifacts under `exports/` remain
  durable
- Step Functions retries Lambda service exceptions and timeouts explicitly with
  exponential backoff, 30-second max delay, and full jitter before routing to
  deterministic failure persistence
- Operators can attach downstream subscriptions or fan-out targets to the
  exported `NovaAlarmTopicArn` topic (`nova-runtime-alarms-{environment}`)
  without modifying the stack, or set `alarm_notification_emails` /
  `ALARM_NOTIFICATION_EMAILS` to auto-create email subscriptions at deploy time
- app-level authorization remains the source of truth

## Transfer and export baseline

- Large uploads remain direct to S3; the public API remains a control plane
  only.
- Current transfer defaults:
  - multipart threshold: `100 MiB`
  - multipart part size: `128 MiB`
  - browser max concurrency: `4`
  - browser sign batch hint floor: `32`, with larger values returned by
    initiate responses when policy allows
  - max upload size: `500 GiB`
- Current export copy behavior uses the inline Lambda path with dedicated copy
  tuning controls (`FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES`,
  `FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY`).
- Clients can inspect the current transfer policy envelope through
  `GET /v1/capabilities/transfers`.

### Current operating plans

- `500 GiB` single upload: `4,000` multipart parts and `500` `sign-parts`
  requests at the current defaults.
- `1 TiB` aggregate burst: treat as two concurrent `500 GiB` uploads, or the
  equivalent control-plane pressure against initiate, sign, introspect,
  complete, and abort.

### Benchmark commands

Run from repository root:

```bash
uv run python scripts/perf/benchmark_transfer_control_plane.py
uv run python scripts/perf/benchmark_export_copy.py
uv run python scripts/perf/benchmark_browser_upload_matrix.py
```

These scripts use fixed inputs, avoid live AWS mutation, and emit JSON for
repeatable comparisons.

### Dashboard surface

The runtime stack publishes `ExportNovaObservabilityDashboardName` for transfer
and export baseline monitoring. The dashboard includes:

- transfer request counts for `uploads_initiate`, `uploads_sign_parts`,
  `uploads_complete`, and `uploads_abort`
- API throttles, API 5xx, and reserved-concurrency saturation
- export queued/copying/finalizing age
- incomplete multipart upload footprint and `>7 day` MPU metrics wired to S3
  Storage Lens metric names
- transfer and export observability dashboard coverage

### Storage Lens prerequisite

- The incomplete MPU widgets require S3 Storage Lens advanced metrics with
  CloudWatch publishing enabled.
- Configuration selection order:
  - context key: `storage_lens_configuration_id`
  - env var: `STORAGE_LENS_CONFIGURATION_ID`
  - fallback: `nova-<environment>-storage-lens`

### Accepted current gaps

- No dedicated API Gateway `429` widget beyond Lambda throttles and API 5xx.
- No quota rejection alarms until quota enforcement exists.
- No Transfer Acceleration spend widget while TA stays disabled by default.
- No worker-lane or DLQ alarms before a worker lane exists.
- No KMS anomaly alarms while SSE-S3 remains the default posture.
