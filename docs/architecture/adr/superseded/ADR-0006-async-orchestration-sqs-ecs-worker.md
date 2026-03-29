---
ADR: 0006
Title: Use SQS + ECS worker for initial async orchestration
Status: Superseded
Superseded-by: "[ADR-0035: Replace generic jobs with export workflows](../ADR-0035-replace-generic-jobs-with-export-workflows.md)"
Version: 1.1
Date: 2026-02-12
Related:
  - "[ADR-0001: Deploy on ECS Fargate behind ALB](./ADR-0001-deployment-on-ecs-fargate-behind-alb.md)"
  - "[ADR-0010: Enqueue failure and readiness semantics](../ADR-0010-enqueue-failure-and-readiness-semantics.md)"
  - "[SPEC-0008: Async jobs and worker orchestration](../../spec/superseded/SPEC-0008-async-jobs-and-worker-orchestration.md)"
References:
  - "[Amazon SQS Developer Guide](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html)"
  - "[Amazon ECS Developer Guide](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html)"
---

> Historical traceability note: this ECS/SQS worker model was superseded by the
> explicit export-workflow baseline in `ADR-0035` and `SPEC-0028`.

## Summary

Adopt SQS + ECS worker as the default async orchestration pattern for the first
production release.

## Context

The service must support background jobs without introducing avoidable platform
complexity. Workloads are moderate-volume, queue-based, and do not require
state-machine orchestration at launch.

## Alternatives

- A: SQS + ECS worker
- B: AWS Step Functions + Lambda
- C: In-process background tasks only

## Decision Framework

| Option | Solution leverage (35%) | Application value (30%) | Maintenance and cognitive load (25%) | Architectural adaptability (10%) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| **A** | **9.5** | **9.0** | **8.5** | **9.0** | **9.00** |
| B | 8.0 | 8.5 | 6.0 | 9.0 | 7.83 |
| C | 5.5 | 5.5 | 7.0 | 4.0 | 5.78 |

## Decision

Choose option A.

Implementation commitments:

- API exposes enqueue/status/cancel endpoints.
- Queue backend defaults to SQS in AWS deployments.
- Worker execution runs on ECS/Fargate.
- Queue publish failures are surfaced synchronously to clients (`503`,
  `queue_unavailable`) and are never treated as successful enqueue.
- Step Functions/Lambda remain out of scope for the initial release.

## Consequences

1. Simple and scalable queue-backed async processing with clear ownership.
2. Fewer moving parts than workflow engines for first release.
3. Future expansion to workflow orchestration remains possible via later ADR.

## Changelog

- 2026-02-12 (v1.0): Initial acceptance.
- 2026-02-12 (v1.1): Added enqueue publish-failure behavior alignment with
  ADR-0010.
