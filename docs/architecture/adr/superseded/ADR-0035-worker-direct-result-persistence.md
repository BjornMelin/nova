---
ADR: 0035
Title: Green-field worker direct result persistence
Status: Superseded
Version: 1.0
Date: 2026-03-19
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API contract](../../spec/superseded/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[SPEC-0028: Worker job lifecycle and direct result path](../spec/SPEC-0028-worker-job-lifecycle-and-direct-result-path.md)"
  - "[Green-field simplification program](../../plan/greenfield-simplification-program.md)"
References:
  - "[Green-field evidence (Framework A)](../../plan/greenfield-evidence/DECISION_FRAMEWORKS_AND_SCORES.md)"
---

> **Superseded target draft**
>
> This draft was superseded before implementation by the explicit export-workflow model in `ADR-0035` / `SPEC-0028`.

## Summary

The worker updates jobs, activity, and related state through **shared
services/repositories**, not via an **internal HTTP callback** into the API.
Winning option: **9.35/10** (Framework A).

## Context

- The worker previously POSTed to an internal HTTP endpoint that delegated to
  the same service layer--adding secrets, retries, latency, and failure modes
  without isolation benefit.
- [GFR-R5](../requirements.md#gfr-r5--worker-must-not-self-call-the-api) forbids
  self-call patterns.
- Execution order: program branch 3.

## Alternatives

- **A:** Keep internal HTTP callback.
- **B:** Introduce async event fan-back for result updates.
- **C:** Direct service/repository updates from worker.

## Decision framework (Framework A)

| Option | Native dependency leverage | Entropy / LOC / file reduction | Reliability / performance | Security / operability | DX / maintainability | Implementation tractability | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A: Keep internal HTTP callback | 2 | 2 | 5 | 4 | 4 | 9 | 3.55 |
| B: Introduce async event fan-back for result updates | 5 | 4 | 8 | 7 | 6 | 5 | 5.85 |
| **C: Direct service/repository updates from worker** | **10** | **9** | **9** | **9** | **10** | **8** | **9.35** |

## Decision

**Option C** is accepted.

Implementation commitments:

- Remove the internal worker → API result callback route and related
  configuration (`JOBS_API_BASE_URL`, worker update token, etc., as
  applicable).
- Wire the worker to shared domain services or repositories used by the API for
  the same mutations.
- Keep poison-message and queue semantics consistent with existing SQS
  contracts.
- Branch `refactor/worker-direct-job-result-updates`.

## Related requirements

- [GFR-R5](../requirements.md#gfr-r5--worker-must-not-self-call-the-api)

## Consequences

1. **Positive:** Less configuration, fewer network failure modes, lower latency
   on completion paths.
2. **Trade-offs:** Worker and API must share a disciplined mutation boundary;
   avoid circular imports; keep transaction boundaries explicit.
3. **Ongoing:** Align with [SPEC-0028](../spec/SPEC-0028-worker-job-lifecycle-and-direct-result-path.md).

## Changelog

- 2026-03-19: Canonical ADR ported from green-field pack ADR-0003.
