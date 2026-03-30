---
ADR: 0038
Title: Reset docs authority
Status: Implemented
Version: 1.0
Date: 2026-03-25
Related:
  - "[ADR-0033: Canonical serverless platform](./ADR-0033-canonical-serverless-platform.md)"
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0016: Hard-cut v1 route contract and route-literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[spec/index.md](../spec/index.md)"
  - "[SPEC-0031: Docs and tests authority reset](../spec/SPEC-0031-docs-and-tests-authority-reset.md)"
---

> **Implementation state:** Implemented on the current branch docs/test surface, with only remaining truth-model cleanup still pending.

## Decision

Reduce the active docs authority set to a small canonical surface and archive or delete historical material from the active path.

## Context

The attached repo’s docs and related contract tests have grown large enough to become a maintenance problem.

## Canonical active set

- root README
- docs/overview
- active ADRs
- active specs
- active runbooks
- active client docs
- current implementation prompts if intentionally kept in-repo

## Consequences

- archive or delete historical plans from the active docs path
- remove tests that exist only to police non-canonical docs sprawl
- keep a much smaller, explicit authority index
