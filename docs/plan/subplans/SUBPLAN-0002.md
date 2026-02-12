# SUBPLAN-0002

- Branch name: `feat/subplan-0002-async-cache-observability-completion`

## Async Jobs + Cache + Observability Completion

Order: 2 of 4
Parent plan: `docs/plan/PLAN.md`
Depends on: `SUBPLAN-0001`

## Persona

Principal Backend Systems Engineer (async orchestration, cache resilience,
operability)

## Objective

Complete the initial production async/caching/observability feature set with
AWS-ready behavior and robust tests.

## Scope

Repository: `~/repos/work/infra-stack/aws-file-transfer-api`

In scope:

- Async job orchestration interfaces
- Queue publisher integration points
- Two-tier cache resiliency and behavior
- EMF metrics and bounded-dimension practices
- Activity rollups and admin summary behavior

## Mandatory Research Inputs

- CloudWatch EMF spec:
  <https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html>
- CloudWatch cardinality guidance:
  <https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Application-Signals-Cardinality.html>
- DynamoDB best practices:
  <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html>
- DynamoDB UpdateItem:
  <https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_UpdateItem.html>
- DynamoDB atomic counters:
  <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/example_dynamodb_Scenario_AtomicCounterOperations_section.html>
- ElastiCache best practices:
  <https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/BestPractices.html>
- SQS request error handling:
  <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/handling-request-errors.html>

## Checklist

### A. Async jobs

- [x] Add enqueue/status/cancel API handlers
- [x] Add memory and SQS publisher abstractions
- [x] Propagate queue publish failures to clients (`503 queue_unavailable`)
- [x] Mark created jobs `failed` when queue publish fails
- [x] Ensure failed enqueue responses are not idempotency replay cached
- [x] Add fail-fast SQS backend configuration validation
- [ ] Add durable job repository backend (DynamoDB)
- [ ] Add worker-facing result update contract and tests

### B. Cache behavior

- [x] Implement local TTL + shared Redis two-tier cache
- [x] Ensure shared cache failures degrade gracefully
- [ ] Add explicit cache hit/miss/fallback metrics

### C. Observability and rollups

- [x] Emit request metrics using EMF-compatible payloads
- [x] Emit request completion logs with request_id and latency
- [x] Implement memory and DynamoDB activity rollup backends
- [x] Ensure readiness excludes feature-flag pass/fail coupling
- [x] Ensure DynamoDB `distinct_event_types` uses first-seen marker increments
- [ ] Add queue lag and worker throughput metrics

### D. Test expansion

- [ ] Add tests for remote auth fail-closed behavior
- [ ] Add tests for Redis outage fallback
- [x] Add tests for activity rollup summary edge cases
- [x] Add tests for enqueue publish-failure behavior and idempotency failure path
- [x] Add tests for readiness behavior with jobs feature disabled

## Acceptance Criteria

- Async endpoint behavior is stable and scope-safe.
- Cache resilience behavior is verified.
- Observability output is low-cardinality and production-safe.
- Remaining gaps are explicitly tracked with implementation tasks.
