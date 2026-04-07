---
ADR: 0010
Title: Fail enqueue on queue publish errors and scope readiness to critical dependencies
Status: Accepted
Version: 1.7
Date: 2026-04-07
Related:
  - "[SPEC-0003: Observability](../spec/SPEC-0003-observability.md)"
  - "[SPEC-0006: JWT/OIDC verification and principal mapping](../spec/SPEC-0006-jwt-oidc-verification-and-principal-mapping.md)"
  - "[SPEC-0010: Observability analytics and activity rollups](../spec/SPEC-0010-observability-analytics-and-activity-rollups.md)"
  - "[SPEC-0018: Runtime configuration and startup validation contract](../spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md)"
  - "[SPEC-0028: Export workflow state machine](../spec/SPEC-0028-export-workflow-state-machine.md)"
References:
  - "[Amazon SQS handling request errors](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/handling-request-errors.html)"
  - "[Amazon SQS error handling and problematic messages](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/best-practices-error-handling.html)"
  - "[Kubernetes liveness, readiness, and startup probes](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/)"
  - "[DynamoDB UpdateItem](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_UpdateItem.html)"
---

## Summary

Adopt fail-fast enqueue semantics for queue publish failures and ensure readiness
checks reflect only critical traffic-serving dependencies. Correct DynamoDB
rollup writes so `distinct_event_types` is accurate under concurrency.

## Context

Three production regressions were identified:

1. Enqueue could return success even when SQS publish failed.
2. Readiness could fail when optional features were intentionally disabled.
3. DynamoDB-backed rollups could report `distinct_event_types = 0` even with
   activity.

These regressions degrade reliability and observability at runtime.

## Alternatives

- A: Keep existing behavior (silent enqueue publish failures, optional feature
  flags in readiness, incomplete rollups)
- B: Fail-fast enqueue (`503 queue_unavailable`), readiness on critical
  dependencies only, conditional marker-based rollup counting
- C: Add asynchronous reconciliation workers to repair queue and rollup
  mismatches after the fact

## Decision Framework

| Option | Solution leverage (35%) | Application value (30%) | Maintenance and cognitive load (25%) | Architectural adaptability (10%) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| A | 4.5 | 3.5 | 6.5 | 4.0 | 4.58 |
| **B** | **9.5** | **9.5** | **8.5** | **9.0** | **9.18** |
| C | 6.0 | 7.0 | 4.5 | 8.0 | 6.03 |

## Decision

Choose option B.

Implementation commitments:

- Queue publish failures for `POST /v1/exports` return `503` and
  `error.code = "queue_unavailable"`.
- Export records created before publish are transitioned to `failed` when
  publish fails.
- `/v1/health/ready` excludes feature flags from pass/fail aggregation.
- `/v1/health/ready` fails `transfer_runtime` when `FILE_TRANSFER_BUCKET` is
  missing/blank or the live S3 bucket probe fails.
- `/v1/health/ready` fails `auth_dependency` when `OIDC_ISSUER`,
  `OIDC_AUDIENCE`, or `OIDC_JWKS_URL` are incomplete or the verifier-owned
  JWKS healthcheck fails.
- Worker updates with `status = succeeded` always normalize `error` to `null`.
- DynamoDB rollups increment `distinct_event_types` only when a first-seen
  event-type marker write succeeds.
- Backend misconfiguration for selected AWS backends fails fast at startup.

## Consequences

1. Client-visible behavior aligns with actual enqueue durability.
2. Valid deployments with optional features disabled stay ready.
3. Dashboard rollups become accurate and concurrency-safe.
4. Startup misconfiguration is detected earlier instead of silently degrading.
5. The in-process bearer verifier now fails readiness closed through the
   canonical `auth_dependency` gate, matching JWT/OIDC verifier authority in
   SPEC-0006.

## Changelog

- 2026-03-31 (v1.5): Canonicalized export enqueue route and record terminology
  to match the implemented `/v1/exports` baseline.
- 2026-04-07 (v1.7): Removed retired `jobs_enabled` wording from the accepted
  readiness regression context.
- 2026-04-06 (v1.6): Updated readiness wording to match the upstream
  verifier-owned auth dependency healthcheck.
- 2026-03-09 (v1.4): Repointed bearer-verifier readiness authority
  references to SPEC-0006.
- 2026-03-05 (v1.3): Added fail-closed bearer-verifier readiness semantics.
- 2026-03-03 (v1.2): Canonicalized enqueue and readiness route references to
  `/v1/*` route surface.
- 2026-02-12 (v1.0): Initial acceptance.
- 2026-02-23 (v1.1): Clarified readiness bucket-configuration rule and worker
  succeeded-state error normalization invariants.
