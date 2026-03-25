---
ADR: 0033
Title: Canonical serverless platform
Status: Accepted
Version: 1.0
Date: 2026-03-25
Supersedes: "[ADR-0033: Green-field single runtime auth authority (superseded)](./superseded/ADR-0033-single-runtime-auth-authority.md)"
Related:
  - "[requirements-wave-2.md](../requirements-wave-2.md)"
  - "[SPEC-0029: Canonical serverless platform](../spec/SPEC-0029-platform-serverless.md)"
  - "[Canonical target state (2026-04)](../../overview/CANONICAL-TARGET-2026-04.md)"
  - "[Green-field wave 2 execution plan](../../plan/GREENFIELD-WAVE-2-EXECUTION.md)"
References:
  - "[RUNBOOK-SERVERLESS-OPERATIONS.md](../../runbooks/RUNBOOK-SERVERLESS-OPERATIONS.md)"
  - "[Breaking changes v2](../../contracts/BREAKING-CHANGES-V2.md)"
---

## Summary

Nova adopts a serverless control-plane platform built around CloudFront, API
Gateway HTTP API, Lambda Web Adapter, Step Functions Standard, DynamoDB, and
S3. This becomes the canonical target runtime because it fits Nova's bursty
control-plane workload and explicit workflow model better than the current
ECS/worker baseline.

## Context

- The current implemented baseline still centers ECS/Fargate, Redis, SQS, and
  a worker callback lifecycle.
- Nova's target workload is a direct-to-S3 transfer control plane plus durable
  export orchestration rather than a long-lived byte-processing service.
- The platform decision must reduce always-on cost, simplify operational
  topology, and align with the explicit export workflow contract.

## Alternatives

- A: Keep ECS/Fargate + ALB + SQS worker as the canonical runtime
- B: Support both ECS and Lambda as parallel first-class target runtimes
- C: Adopt one canonical serverless runtime using HTTP API + Lambda + Step
  Functions

## Decision Framework

### Option Scoring

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| A | 4 | 5 | 4 | 5 | 4.45 |
| B | 6 | 6 | 3 | 7 | 5.45 |
| **C** | **10** | **9** | **9** | **9** | **9.35** |

`weighted total = (leverage * 0.35) + (value * 0.30) + (maintenance * 0.25) + (adaptability * 0.10)`

## Decision

**Option C** is accepted.

Implementation commitments:

- Make the serverless stack the sole canonical target platform in active
  target-state docs.
- Add first-class workflow and CDK/IaC components that match the new runtime.
- Remove ECS/worker/Redis assumptions from the target-state architecture and
  release flow as later branches land.

## Related Requirements

- [Product requirements](../requirements-wave-2.md#product-requirements)
- [Architecture requirements](../requirements-wave-2.md#architecture-requirements)
- [Quality requirements](../requirements-wave-2.md#quality-requirements)

## Consequences

1. Positive outcomes: lower idle cost, simpler scaling behavior, and tighter
   alignment between API coordination and workflow orchestration.
2. Trade-offs/costs: Lambda packaging, Step Functions modeling, and IaC changes
   become mandatory; long-lived ECS-centric operational habits are no longer the
   canonical path.
3. Ongoing considerations: concurrency limits, latency tuning, and workflow
   observability must be designed as first-class operational concerns.

## Changelog

- 2026-03-25: Initial target-state ADR added for the wave-2 hard cut.
