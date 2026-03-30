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

> **Implementation state:** Implemented on the current branch docs/test surface, with only remaining truth-model cleanup still pending.

## Problem

The repo has too many active docs and too many tests whose only job is to enforce that sprawl.

## Decision

Keep a smaller active authority set and archive or delete the rest.

## Active docs classes

- current overview
- active ADRs
- active specs
- active runbooks
- active SDK/client docs
- implementation prompts if intentionally retained

## Test rule

Keep tests that protect executable behaviour, contract compatibility for the current API, SDK generation correctness, and platform safety.
Delete or archive tests whose primary purpose is to enforce legacy planning/history surfaces.
