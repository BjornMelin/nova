---
Spec: 0010
Title: Observability Analytics and Activity Rollups
Status: Active
Version: 1.2
Date: 2026-02-12
Related:
  - "[ADR-0009: EMF + DynamoDB + CloudWatch observability stack](../adr/ADR-0009-observability-analytics-emf-dynamodb-cloudwatch.md)"
  - "[SPEC-0003: Observability](./SPEC-0003-observability.md)"
References:
  - "[CloudWatch EMF specification](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html)"
  - "[CloudWatch cardinality guidance](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Application-Signals-Cardinality.html)"
  - "[DynamoDB best practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)"
---

## 1. Metric emission

EMF payloads MUST include:

- metric namespace
- timestamp
- bounded dimension sets
- metric definitions and values

High-cardinality fields (for example `request_id`, `user_id`) MUST NOT be used as
metric dimensions.

## 2. Activity rollups

Rollups SHOULD aggregate per-day totals for dashboard usage:

- events_total
- active_users_today
- distinct_event_types

AWS deployments SHOULD use DynamoDB-backed rollups.

When using DynamoDB rollups:

- `events_total` MUST use atomic counters (`UpdateItem` + `ADD`).
- `active_users_today` MUST be incremented only on first user-day marker
  creation.
- `distinct_event_types` MUST be incremented only on first event-type-day marker
  creation.
- Marker writes MUST use conditional expressions to keep counts accurate under
  concurrency.
- Marker records SHOULD use short TTLs to limit key accumulation while
  preserving day-level correctness.

## 3. Dashboard requirements

Dashboards SHOULD cover:

- API traffic, error rate, and latency
- async queue backlog/lag
- worker throughput and failures
- activity trend views

## 4. Alarm requirements

Alarms SHOULD be defined for:

- sustained 5xx spikes
- latency SLO breach
- queue lag/backlog thresholds
- worker failure rate anomalies

## 5. Traceability

- [FR-0007](../requirements.md#fr-0007-observability-and-analytics)
- [NFR-0003](../requirements.md#nfr-0003-operability)
