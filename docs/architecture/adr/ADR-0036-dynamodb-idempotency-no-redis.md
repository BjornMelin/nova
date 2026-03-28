# ADR-0036 -- DynamoDB idempotency and transient state, no Redis

> **Implementation state:** Approved target-state ADR. The current codebase still includes Redis-backed correctness paths; this ADR defines the hard cut away from them.

## Status
Accepted

## Decision

Use DynamoDB as the durable persistence layer for idempotency and workflow state. Remove Redis from the canonical runtime. If local hot-cache behaviour is useful, keep it as an in-process optimization only.

## Context

The attached repo still treats Redis as part of the correctness path for shared claim/replay behaviour.

## Why this wins

- one less distributed runtime dependency
- lower ops burden
- simpler secrets/config surface
- better fit for the canonical serverless target
- easier local and integration testing

## Important caveat

DynamoDB TTL deletion is eventual, so code must treat expiration as an application concern and filter expired items explicitly.

## Consequences

- delete Redis URL/config/runtime contract
- delete cache-specific infra and docs from the canonical path
- simplify idempotency tests and startup validation
