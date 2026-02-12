---
ADR: 0009
Title: Observability stack: EMF metrics, DynamoDB rollups, CloudWatch dashboards
Status: Accepted
Version: 1.2
Date: 2026-02-12
Related:
  - "[ADR-0010: Enqueue failure and readiness semantics](./ADR-0010-enqueue-failure-and-readiness-semantics.md)"
  - "[SPEC-0010: Observability analytics and activity rollups](../spec/SPEC-0010-observability-analytics-and-activity-rollups.md)"
  - "[ADR-0001: ECS/Fargate deployment behind ALB](./ADR-0001-deployment-on-ecs-fargate-behind-alb.md)"
References:
  - "[CloudWatch EMF specification](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html)"
  - "[CloudWatch cardinality guidance](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Application-Signals-Cardinality.html)"
  - "[DynamoDB best practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)"
---

## Summary

Adopt EMF metrics + CloudWatch dashboards/alarms and store daily activity
rollups in DynamoDB for low-cardinality analytics.

## Context

The service needs production-operable visibility for latency/error/SQS backlog,
plus user activity trend insights without high-cardinality custom metric spend.

## Alternatives

- A: Logs-only observability
- B: EMF metrics + dashboards + DynamoDB daily rollups
- C: Full external observability platform at launch

## Decision Framework

| Option | Solution leverage (35%) | Application value (30%) | Maintenance and cognitive load (25%) | Architectural adaptability (10%) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| A | 5.5 | 6.5 | 7.5 | 5.0 | 6.18 |
| **B** | **9.0** | **9.5** | **8.5** | **9.0** | **9.03** |
| C | 7.0 | 8.5 | 5.5 | 9.5 | 7.20 |

## Decision

Choose option B.

Implementation commitments:

- Emit structured logs with `request_id`.
- Emit EMF-compatible low-cardinality metrics.
- Record queue lag from worker processing transitions
  (`jobs_queue_lag_ms`) and worker update throughput counters.
- Track daily activity rollups in DynamoDB for dashboard summaries.
- Keep rollup counters accurate using conditional marker writes for first-seen
  user/day and event-type/day records.
- Define and maintain CloudWatch dashboards and alarms as release gates.

## Consequences

1. Strong production observability with moderate implementation complexity.
2. Better cost control than high-cardinality custom metrics strategy.
3. Requires dashboard/alarm IaC ownership in container-craft.

## Changelog

- 2026-02-12 (v1.0): Initial acceptance.
- 2026-02-12 (v1.1): Added explicit marker-based rollup correctness commitment.
- 2026-02-12 (v1.2): Added explicit queue lag and worker throughput metric
  commitments.
