---
ADR: 0034
Title: Eliminate auth service and session auth
Status: Accepted
Version: 1.0
Date: 2026-03-25
Supersedes: "[ADR-0034: Green-field bearer JWT public auth contract (superseded)](./superseded/ADR-0034-bearer-jwt-public-auth-contract.md)"
Related:
  - "[requirements-wave-2.md](../requirements-wave-2.md)"
  - "[SPEC-0027: Public API v2](../spec/SPEC-0027-public-api-v2.md)"
  - "[Breaking changes v2](../../contracts/BREAKING-CHANGES-V2.md)"
  - "[Canonical target state (2026-04)](../../overview/CANONICAL-TARGET-2026-04.md)"
References:
  - "[Canonical client package layout](../../clients/CLIENT-SDK-CANONICAL-PACKAGES.md)"
  - "[Green-field wave 2 execution plan](../../plan/GREENFIELD-WAVE-2-EXECUTION.md)"
---

## Summary

Nova removes the dedicated auth service and all session-style public auth
surrogates, keeping one bearer-JWT-only public auth model verified in-process
by the main API runtime. This simplifies the external contract, removes
duplicate auth components, and makes SDK and OpenAPI generation materially
simpler.

## Context

- The current baseline still carries multiple auth modes, a dedicated auth
  service, and session/header surrogates such as `session_id`,
  `X-Session-Id`, and `X-Scope-Id`.
- Those surrogates complicate client behavior, OpenAPI documentation, SDK
  generation, and deployment topology.
- The target-state system already assumes one public API runtime and one client
  auth model across TypeScript, Python, R, browser, and Dash consumers.

## Alternatives

- A: Keep the dedicated auth service and remote verification flow
- B: Keep hybrid auth with both bearer JWT and session/same-origin semantics
- C: Use bearer JWT only and verify it in-process in the main API

## Decision Framework

### Option Scoring

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| A | 3 | 5 | 3 | 4 | 3.85 |
| B | 5 | 6 | 4 | 5 | 5.10 |
| **C** | **10** | **10** | **9** | **9** | **9.65** |

`weighted total = (leverage * 0.35) + (value * 0.30) + (maintenance * 0.25) + (adaptability * 0.10)`

## Decision

**Option C** is accepted.

Implementation commitments:

- Delete the dedicated auth service and auth-only SDK packages.
- Remove session/same-origin auth inputs from the public contract.
- Keep one bearer-JWT-only external auth model across the API, docs, and SDKs.

## Related Requirements

- [Product requirements](../requirements-wave-2.md#product-requirements)
- [Architecture requirements](../requirements-wave-2.md#architecture-requirements)
- [Quality requirements](../requirements-wave-2.md#quality-requirements)

## Consequences

1. Positive outcomes: one auth model for all clients, one fewer deployable
   service, and a cleaner public contract.
2. Trade-offs/costs: all remaining session-style integration assumptions must
   be removed, and migration is intentionally breaking.
3. Ongoing considerations: JWT verification, principal normalization, and
   authorization rules must remain explicit in the main API and not drift into
   multiple parallel implementations.

## Changelog

- 2026-03-25: Initial target-state ADR added for the wave-2 hard cut.
