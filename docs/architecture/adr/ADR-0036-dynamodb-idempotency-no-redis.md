---
ADR: 0036
Title: DynamoDB idempotency and transient state, no Redis
Status: Implemented
Version: 1.0
Date: 2026-03-25
Related:
  - "[ADR-0033: Canonical serverless platform](./ADR-0033-canonical-serverless-platform.md)"
  - "[SPEC-0029: Canonical serverless platform](../spec/SPEC-0029-platform-serverless.md)"
  - "[ADR-0035: Replace generic jobs with export workflows](./ADR-0035-replace-generic-jobs-with-export-workflows.md)"
---

> **Implementation state:** Implemented in the current repository baseline, with only residual Redis-era references and legacy assets still requiring cleanup.

## Decision

Use DynamoDB as the durable persistence layer for idempotency and workflow
state. Keep Redis out of the canonical runtime. If local hot-cache behaviour
is useful, keep it as an in-process optimization only.

## Context

The current repository already uses DynamoDB-backed idempotency as the active
correctness path; the remaining cleanup is to eliminate stale Redis-era docs
and legacy assets from active surfaces.

## Why this wins

- one less distributed runtime dependency
- lower ops burden
- simpler secrets/config surface
- better fit for the canonical serverless target
- easier local and integration testing

## Important caveat

DynamoDB TTL deletion is eventual, so code must treat expiration as an application concern and filter expired items explicitly.

## Consequences

- keep Redis URL/config/runtime contract out of active docs and runtime truth
- retire cache-specific legacy infra/docs from the canonical path
- keep idempotency tests and startup validation aligned to DynamoDB-backed
  requirements
