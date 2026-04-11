---
SPEC: 0031
Title: Docs and tests authority reset
Status: Implemented
Version: 1.0
Date: 2026-03-25
Related:
  - "[ADR-0033: Canonical serverless platform](../adr/ADR-0033-canonical-serverless-platform.md)"
  - "[ADR-0038: Reset docs authority](../adr/ADR-0038-docs-authority-reset.md)"
---

> **Implementation state:** Implemented as the active docs/test authority model.

## Problem

The repo has too many active docs and too many tests whose only job is to enforce that sprawl.

## Decision

Keep a smaller active authority set and archive or delete the rest.
Keep active validation and contract tests focused on production truth for the
implemented serverless baseline rather than primarily enforcing deleted-surface
absence.

## Active docs classes

- current overview
- active ADRs
- active specs
- active runbooks
- active SDK/client docs
- stable current-state requirements / PRD summaries
- implementation prompts only when intentionally retained as historical context

## Test rule

Keep tests that protect executable behaviour, contract compatibility for the
current API, SDK generation correctness, and platform safety.
Delete or archive tests whose primary purpose is to enforce legacy planning/
history surfaces.
Require active docs routers and downstream guides to point at deploy-output
authority for runtime base URL and deployed release provenance.
