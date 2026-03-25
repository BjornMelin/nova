---
Spec: 0031
Title: Docs and tests authority reset
Status: Active
Version: 1.0
Date: 2026-03-25
Supersedes: ""
Related:
  - "[requirements-wave-2.md](../requirements-wave-2.md)"
  - "[ADR-0038: Reset docs authority](../adr/ADR-0038-docs-authority-reset.md)"
  - "[Active docs index](../../overview/ACTIVE-DOCS-INDEX.md)"
  - "[Green-field wave 2 execution plan](../../plan/GREENFIELD-WAVE-2-EXECUTION.md)"
References:
  - "[Breaking changes v2](../../contracts/BREAKING-CHANGES-V2.md)"
  - "[Dependency leverage audit](../../overview/DEPENDENCY-LEVERAGE-AUDIT.md)"
---

## 1. Purpose

Define the approved target-state rules for the active docs surface and for the
tests that exist to protect docs/governance behavior.

## 2. Problem

The repo accumulated too many active docs and too many tests whose primary job
was to police that sprawl rather than protect executable behavior or live
contracts.

## 3. Decision

Keep a smaller active authority set and archive or delete the rest.

## 4. Active docs classes

- current overview and active indexes
- active ADRs
- active specs
- active runbooks
- active SDK/client docs
- implementation prompts only when intentionally retained for branch execution

## 5. Test rule

- keep tests that protect executable behavior
- keep tests that protect current public contract compatibility
- keep tests that protect SDK generation correctness
- keep tests that protect platform safety
- delete or archive tests whose primary purpose is enforcing legacy
  planning/history surfaces

## 6. Traceability

- [Repo requirements](../requirements-wave-2.md#repo-requirements)
- [Quality requirements](../requirements-wave-2.md#quality-requirements)
- [Architecture requirements](../requirements-wave-2.md#architecture-requirements)
