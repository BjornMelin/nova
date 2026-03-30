---
ADR: 0008
Title: Runtime support levels: sidecar GA, embedded bridge, standalone beta
Status: Accepted
Version: 1.0
Date: 2026-02-12
Related:
  - "[ADR-0001: Deploy on ECS Fargate behind ALB](./superseded/ADR-0001-deployment-on-ecs-fargate-behind-alb.md)"
  - "[SPEC-0000: HTTP API contract](../spec/superseded/SPEC-0000-http-api-contract.md)"
References:
  - "[FastAPI deployment workers](https://fastapi.tiangolo.com/deployment/server-workers/)"
---

## Summary

Define explicit runtime support levels for initial release:

- Sidecar runtime: GA (primary)
- Embedded bridge runtime: supported migration bridge
- Standalone API runtime: beta with smoke coverage

## Context

The program serves same-origin browser workloads first, while preserving a clean
migration path for existing embedded integrations and new standalone consumers.

## Alternatives

- A: Sidecar only
- B: Sidecar + embedded + standalone with explicit support tiers
- C: Standalone-only service model

## Decision Framework

| Option | Solution leverage (35%) | Application value (30%) | Maintenance and cognitive load (25%) | Architectural adaptability (10%) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| A | 8.0 | 8.0 | 8.5 | 6.0 | 7.95 |
| **B** | **9.5** | **9.5** | **8.0** | **9.5** | **9.13** |
| C | 7.5 | 8.5 | 6.5 | 9.0 | 7.70 |

## Decision

Choose option B.

Implementation commitments:

- Sidecar is the default production deployment path.
- Embedded bridge remains available during migration windows.
- Standalone mode is documented and smoke-tested, but not GA-hardening target in
  initial release.

## Consequences

1. Preserves same-origin simplicity for browser clients.
2. Reduces migration risk for existing embedded integrations.
3. Requires explicit support matrix management in docs and release notes.

## Changelog

- 2026-02-12 (v1.0): Initial acceptance.
