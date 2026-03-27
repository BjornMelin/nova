---
ADR: 0037
Title: Consolidate SDK generation and package layout
Status: Accepted
Version: 1.0
Date: 2026-03-25
Supersedes: "[ADR-0037: Green-field async-first public surface (superseded)](./superseded/ADR-0037-async-first-public-surface.md)"
Related:
  - "[requirements-wave-2.md](../requirements-wave-2.md)"
  - "[SPEC-0030: SDK generation and package layout](../spec/SPEC-0030-sdk-generation-and-package-layout.md)"
  - "[Canonical client package layout](../../clients/CLIENT-SDK-CANONICAL-PACKAGES.md)"
  - "[Breaking changes v2](../../contracts/BREAKING-CHANGES-V2.md)"
References:
  - "[Dependency leverage audit](../../overview/DEPENDENCY-LEVERAGE-AUDIT.md)"
  - "[Green-field wave 2 execution plan](../../plan/GREENFIELD-WAVE-2-EXECUTION.md)"
---

## Summary

Nova adopts one canonical SDK package per language and removes the auth/file
split plus the bespoke TypeScript runtime package. The target SDK stacks are
`@hey-api/openapi-ts` for TypeScript, `openapi-python-client` for Python, and a
thin `httr2` wrapper for R.

## Context

- The current baseline still carries split auth/file SDK families and a custom
  TypeScript runtime package.
- Those packages increase release complexity, package discovery cost, and
  maintenance burden across examples, publishing, and documentation.
- The target-state public contract is also simplifying, which makes a unified
  per-language SDK layout more tractable.

## Alternatives

- A: Keep the split auth/file SDK families and existing TS runtime package
- B: Partially unify packages but keep custom TS runtime behavior
- C: Use one package per language and lean on the strongest native generator or
  thin-wrapper strategy per language

## Decision Framework

### Option Scoring

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| A | 3 | 5 | 3 | 4 | 3.75 |
| B | 6 | 7 | 5 | 6 | 6.10 |
| **C** | **10** | **9** | **9** | **9** | **9.35** |

`weighted total = (leverage * 0.35) + (value * 0.30) + (maintenance * 0.25) + (adaptability * 0.10)`

## Decision

**Option C** is accepted.

Implementation commitments:

- Rename the canonical SDK package directories to the target names.
- Publish the canonical R package as `nova` from `packages/nova_sdk_r`.
- Delete auth SDK packages and `packages/nova_sdk_fetch`.
- Keep release tooling generator-oriented and language-specific rather than
  patch-heavy and package-split aware.

## Related Requirements

- [Product requirements](../requirements-wave-2.md#product-requirements)
- [Architecture requirements](../requirements-wave-2.md#architecture-requirements)
- [Repo requirements](../requirements-wave-2.md#repo-requirements)

## Consequences

1. Positive outcomes: cleaner package discovery, fewer release targets, and
   better leverage from language-native tooling.
2. Trade-offs/costs: package renames are intentionally breaking and require
   example/docs cleanup across all clients.
3. Ongoing considerations: the final published names and import guidance must
   remain explicit in client docs and release tooling.

## Changelog

- 2026-03-25: Initial target-state ADR added for the wave-2 hard cut.
