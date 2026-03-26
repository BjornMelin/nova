---
ADR: 0035
Title: Replace generic jobs with export workflows
Status: Accepted
Version: 1.0
Date: 2026-03-25
Supersedes: "[ADR-0035: Green-field worker direct result persistence (superseded)](./superseded/ADR-0035-worker-direct-result-persistence.md)"
Related:
  - "[requirements-wave-2.md](../requirements-wave-2.md)"
  - "[SPEC-0027: Public API v2](../spec/SPEC-0027-public-api-v2.md)"
  - "[SPEC-0028: Export workflow state machine](../spec/SPEC-0028-export-workflow-state-machine.md)"
  - "[Breaking changes v2](../../contracts/BREAKING-CHANGES-V2.md)"
References:
  - "[Canonical target state (2026-04)](../../overview/CANONICAL-TARGET-2026-04.md)"
  - "[Green-field wave 2 execution plan](../../plan/GREENFIELD-WAVE-2-EXECUTION.md)"
---

## Summary

Nova replaces the generic jobs API with explicit export workflow resources and
typed workflow states. This removes a fake abstraction, simplifies generated
clients, and aligns the public contract with the only workflow class the system
actually needs to expose.

## Context

- The current baseline still exposes a generic typed string plus arbitrary payload
  contract.
- In practice, the system has one meaningful async workload family for external
  consumers: exports derived from uploaded content.
- The baseline also includes an internal worker callback route, which leaks
  worker lifecycle concerns into the runtime model and downstream docs.

## Alternatives

- A: Keep the generic jobs contract and improve validation only
- B: Keep jobs as the public abstraction but add stronger enums and wrappers
- C: Remove generic jobs from the public surface and expose explicit export
  workflows instead

## Decision Framework

### Option Scoring

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| A | 4 | 5 | 4 | 5 | 4.45 |
| B | 6 | 6 | 5 | 6 | 5.75 |
| **C** | **10** | **9** | **9** | **9** | **9.35** |

`weighted total = (leverage * 0.35) + (value * 0.30) + (maintenance * 0.25) + (adaptability * 0.10)`

## Decision

**Option C** is accepted.

Implementation commitments:

- Delete the generic jobs public API from active target-state docs.
- Replace the callback-driven worker lifecycle with explicit workflow state
  ownership.
- Make export workflows the only externally supported durable async resource
  family.

## Related Requirements

- [Product requirements](../requirements-wave-2.md#product-requirements)
- [Architecture requirements](../requirements-wave-2.md#architecture-requirements)
- [Quality requirements](../requirements-wave-2.md#quality-requirements)

## Consequences

1. Positive outcomes: a clearer client contract, better SDK generation, and a
   simpler mental model for operators and downstream users.
2. Trade-offs/costs: the public API becomes intentionally breaking for consumers
   of generic jobs, and any internal workflow assumptions must be rewritten.
3. Ongoing considerations: export state transitions, retry behavior, and
   operator diagnostics must be modeled explicitly rather than delegated to a
   generic worker/job wrapper.

## Changelog

- 2026-03-25: Initial target-state ADR added for the wave-2 hard cut.
