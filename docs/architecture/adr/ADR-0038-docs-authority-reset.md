---
ADR: 0038
Title: Reset docs authority
Status: Accepted
Version: 1.0
Date: 2026-03-25
Supersedes: "[ADR-0038: Green-field SDK architecture by language (superseded)](./superseded/ADR-0038-sdk-architecture-by-language.md)"
Related:
  - "[requirements-wave-2.md](../requirements-wave-2.md)"
  - "[SPEC-0031: Docs and tests authority reset](../spec/SPEC-0031-docs-and-tests-authority-reset.md)"
  - "[Active docs index](../../overview/ACTIVE-DOCS-INDEX.md)"
  - "[Green-field wave 2 execution plan](../../plan/GREENFIELD-WAVE-2-EXECUTION.md)"
References:
  - "[Breaking changes v2](../../contracts/BREAKING-CHANGES-V2.md)"
  - "[Dependency leverage audit](../../overview/DEPENDENCY-LEVERAGE-AUDIT.md)"
---

## Summary

Nova reduces its active docs authority surface to a smaller canonical set and
archives or deletes historical and duplicate material from active-looking paths.
The goal is to make the repository easier to navigate and cheaper to keep in
sync as the wave-2 hard cut lands.

## Context

- The current baseline docs and docs-policing tests have grown large enough to
  become their own maintenance burden.
- Multiple planning, history, and authority layers now compete for attention,
  which raises the chance that future branches update the wrong files.
- The target-state program wants one explicit active authority set plus clear
  historical/superseded traceability.

## Alternatives

- A: Keep the broad current docs surface and add more policing tests
- B: Keep most docs in place but relabel them more carefully
- C: Shrink the active authority set and move non-canonical material out of the
  active path

## Decision Framework

### Option Scoring

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| A | 3 | 4 | 2 | 4 | 3.10 |
| B | 5 | 6 | 5 | 6 | 5.45 |
| **C** | **9** | **9** | **9** | **9** | **9.00** |

`weighted total = (leverage * 0.35) + (value * 0.30) + (maintenance * 0.25) + (adaptability * 0.10)`

## Decision

**Option C** is accepted.

Implementation commitments:

- Keep an explicit active-docs index and a separate historical/superseded area.
- Move stale authority docs out of active-looking locations.
- Remove or rewrite tests that mainly police deprecated docs/process sprawl.

## Related Requirements

- [Repo requirements](../requirements-wave-2.md#repo-requirements)
- [Quality requirements](../requirements-wave-2.md#quality-requirements)
- [Architecture requirements](../requirements-wave-2.md#architecture-requirements)

## Consequences

1. Positive outcomes: clearer operator/developer navigation and lower docs-sync
   cost.
2. Trade-offs/costs: archive moves and index updates are disruptive and require
   careful path hygiene.
3. Ongoing considerations: active docs must stay small and truthful; new
   branches should update only the canonical files for their behavior changes.

## Changelog

- 2026-03-25: Initial target-state ADR added for the wave-2 hard cut.
