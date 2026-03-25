---
ADR: 0036
Title: DynamoDB idempotency and transient state, no Redis
Status: Accepted
Version: 1.0
Date: 2026-03-25
Supersedes: "[ADR-0036: Green-field native FastAPI OpenAPI contract expression (superseded)](./superseded/ADR-0036-native-fastapi-openapi-contract.md)"
Related:
  - "[requirements-wave-2.md](../requirements-wave-2.md)"
  - "[SPEC-0029: Canonical serverless platform](../spec/SPEC-0029-platform-serverless.md)"
  - "[Breaking changes v2](../../contracts/BREAKING-CHANGES-V2.md)"
  - "[Canonical target state (2026-04)](../../overview/CANONICAL-TARGET-2026-04.md)"
References:
  - "[Green-field wave 2 execution plan](../../plan/GREENFIELD-WAVE-2-EXECUTION.md)"
  - "[RUNBOOK-SERVERLESS-OPERATIONS.md](../../runbooks/RUNBOOK-SERVERLESS-OPERATIONS.md)"
---

## Summary

Nova uses DynamoDB as the durable state and idempotency store for the canonical
runtime and removes Redis from the correctness path. This reduces operational
surface area and aligns persistent state management with the serverless target
platform.

## Context

- The current baseline still treats Redis as part of shared correctness for
  claim/replay behavior.
- The target platform is already centered on DynamoDB, Step Functions, and
  Lambda, making Redis an extra distributed dependency with separate secrets,
  infra, and operational failure modes.
- Expiration semantics still matter, but DynamoDB TTL is eventual and must be
  handled explicitly in application logic.

## Alternatives

- A: Keep Redis as the canonical shared idempotency and transient state system
- B: Keep Redis for correctness and add DynamoDB only for workflow state
- C: Use DynamoDB as the durable source of truth and keep any hot cache strictly
  in-process and optional

## Decision Framework

### Option Scoring

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| A | 4 | 5 | 3 | 5 | 4.20 |
| B | 5 | 6 | 3 | 6 | 4.95 |
| **C** | **9** | **9** | **9** | **9** | **9.00** |

`weighted total = (leverage * 0.35) + (value * 0.30) + (maintenance * 0.25) + (adaptability * 0.10)`

## Decision

**Option C** is accepted.

Implementation commitments:

- Remove Redis from the canonical runtime contract and active target-state docs.
- Use DynamoDB for workflow state and idempotency records.
- Treat expiration as an application concern instead of assuming immediate TTL
  deletion.

## Related Requirements

- [Architecture requirements](../requirements-wave-2.md#architecture-requirements)
- [Repo requirements](../requirements-wave-2.md#repo-requirements)
- [Quality requirements](../requirements-wave-2.md#quality-requirements)

## Consequences

1. Positive outcomes: one less distributed runtime dependency, lower ops
   burden, and better alignment with the canonical platform.
2. Trade-offs/costs: TTL cleanup is eventual and must not be treated as
   immediate deletion; cache-like performance shortcuts must stay non-authoritative.
3. Ongoing considerations: schema design, expiry filtering, and idempotency
   conflict semantics must remain explicit in implementation and tests.

## Changelog

- 2026-03-25: Initial target-state ADR added for the wave-2 hard cut.
