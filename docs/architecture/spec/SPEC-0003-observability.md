---
Spec: 0003
Title: Observability
Status: Active
Version: 1.2
Date: 2026-02-12
Related:
  - "[ADR-0009: Observability stack](../adr/ADR-0009-observability-analytics-emf-dynamodb-cloudwatch.md)"
  - "[SPEC-0010: Observability analytics and activity rollups](./SPEC-0010-observability-analytics-and-activity-rollups.md)"
References:
  - "[CloudWatch EMF specification](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html)"
  - "[CloudWatch cardinality guidance](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Application-Signals-Cardinality.html)"
---

## 1. Health and readiness

Service MUST expose:

- `GET /healthz` for liveness
- `GET /readyz` for readiness checks of critical dependencies

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
- enqueue latency and queue-oriented counters

Metrics dimensions MUST avoid high-cardinality identifiers.

## 4. Analytics rollups

Daily rollup summaries SHOULD include:

- events total
- active users today
- distinct event types

In AWS deployments, DynamoDB SHOULD back rollups.

## 5. Dashboards and alarms

Release readiness requires CloudWatch dashboards/alarms for:

- API latency/error/traffic
- queue backlog and age
- worker success/failure trends
- activity rollup trends

## 6. Traceability

- [FR-0002](../requirements.md#fr-0002-operational-endpoints)
- [FR-0007](../requirements.md#fr-0007-observability-and-analytics)
- [NFR-0003](../requirements.md#nfr-0003-operability)
