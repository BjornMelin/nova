# ADR-0038 -- Reset docs authority

> **Implementation state:** Implemented on the current branch docs/test surface, with only remaining truth-model cleanup still pending.

## Status
Accepted

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
