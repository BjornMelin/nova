---
Spec: 0003
Title: Observability
Status: Active
Version: 2.2
Date: 2026-04-08
Related:
  - "[ADR-0009: Observability stack](../adr/ADR-0009-observability-analytics-emf-dynamodb-cloudwatch.md)"
  - "[SPEC-0010: Observability analytics and activity rollups](./SPEC-0010-observability-analytics-and-activity-rollups.md)"
References:
  - "[CloudWatch EMF specification](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html)"
  - "[CloudWatch cardinality guidance](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Application-Signals-Cardinality.html)"
---

## 1. Health and readiness

Service MUST expose:

- `GET /v1/health/live` for liveness
- `GET /v1/health/ready` for readiness checks of the current runtime
  dependencies

Readiness rules:

- `/v1/health/ready` `ok` MUST reflect the current runtime checks reported in
  the response body.
- Feature flags MUST NOT drive readiness pass/fail.
- Optional feature disablement MUST NOT mark service unready.
- Missing/blank `FILE_TRANSFER_BUCKET` MUST fail the `transfer_runtime`
  readiness check.
- `auth_dependency` MUST reflect the configured verifier's live readiness
  result, using the verifier-owned JWKS lifecycle/readiness APIs rather than
  a Nova-owned configuration-only or private-JWKS probe path.
- Readiness responses MUST report live traffic gates only; configuration-only
  diagnostics do not belong in the readiness checks payload.

## 2. Structured logging requirements

Each request log SHOULD include:

- `request_id`
- method and path
- status code and outcome
- latency
- active auth mode

Sensitive fields MUST be redacted.

## 3. Metrics requirements

Metrics MUST include at least:

- request counts by route and status
- endpoint latency
- auth failures
- quota rejection counters
- request-level transfer/export application counters
- stale upload-session reconciliation counters
- export enqueue latency and queue-oriented counters
- export queue lag and status-age counters observed from the export worker lane
  (`exports_queue_lag_ms`, `exports_queued_age_ms`,
  `exports_copying_age_ms`, `exports_finalizing_age_ms`)
- export worker message lag plus invalid-message, unresolved-invalid,
  poison-terminalized, poison-stale/orphaned, retry-exhaustion, abort, and
  worker batch-failure counters (`exports_worker_message_lag_ms`,
  `exports_worker_messages_invalid_total`,
  `exports_worker_messages_invalid_unresolved_total`,
  `exports_worker_poison_terminalized_total`,
  `exports_worker_poison_stale_total`,
  `exports_worker_poison_orphaned_total`,
  `exports_worker_retry_exhausted_total`,
  `exports_worker_abort_total`,
  `exports_worker_message_failures_total`)
- export status-update throughput counters (`exports_status_updates_total` and
  per-status variants)

Metrics dimensions MUST avoid high-cardinality identifiers.

EMF payload metadata (`_aws`) and metric fields MUST be emitted as top-level
structured log members, not nested JSON strings.

## 4. Analytics rollups

Daily rollup summaries SHOULD include:

- events total
- active users today
- distinct event types

In AWS deployments, DynamoDB SHOULD back rollups.

## 5. Dashboards and alarms

Release readiness requires CloudWatch dashboards/alarms for:

- API latency/error/traffic
- export queue backlog and age
- export worker malformed-message, poison-recovery, and abort trends
- export status-transition and failure trends
- activity rollup trends
- incomplete multipart upload storage older than seven days
- DynamoDB throttles across upload-session and transfer-usage tables
- transfer spend budget notifications

## 6. Traceability

- [FR-0002](../requirements.md#fr-0002-operational-endpoints)
- [FR-0007](../requirements.md#fr-0007-observability-and-analytics)
- [NFR-0003](../requirements.md#nfr-0003-operability)
