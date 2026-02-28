---
ADR: 0012
Title: Preserve ECS and SQS runtime scope and exclude Lambda orchestration
Status: Accepted
Version: 1.1
Date: 2026-02-24
Related:
  - "[ADR-0001: Deployment on ECS Fargate behind ALB](./ADR-0001-deployment-on-ecs-fargate-behind-alb.md)"
  - "[ADR-0006: Async orchestration SQS + ECS worker](./ADR-0006-async-orchestration-sqs-ecs-worker.md)"
  - "[ADR-0011: Hybrid CI/CD with GitHub and AWS promotion](./ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[SPEC-0008: Async jobs and worker orchestration](../spec/SPEC-0008-async-jobs-and-worker-orchestration.md)"
References:
  - "[AWS Lambda developer guide](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html)"
  - "[Amazon ECS best practices for IAM roles](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/security-iam-roles.html)"
  - "[AWS Well-Architected reliability pillar](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html)"
---

## Summary

Runtime request handling and async job execution remain ECS/Fargate plus SQS
only for this release track. Lambda or Step Functions orchestration is excluded
to avoid introducing a second runtime control plane during hard cutover.

## Context

- Business/product need: complete hard cutover quickly with predictable
  operations and low-maintenance runtime paths.
- Technical and operational constraints: existing runbooks, metrics, and IAM
  controls are built around ECS tasks, ALB routing, and SQS worker semantics.
- Rejected assumptions and risks discovered: adding Lambda in initial rollout
  increases IAM surface, deployment permutations, and incident triage complexity
  without proportional release value.
- Related docs: [ADR-0006](./ADR-0006-async-orchestration-sqs-ecs-worker.md),
  [SPEC-0008](../spec/SPEC-0008-async-jobs-and-worker-orchestration.md), and
  [requirements](../requirements.md).

## Alternatives

- A: Keep ECS/Fargate plus SQS runtime scope only.
- B: Add Lambda/Step Functions runtime orchestration in initial rollout.
- C: Use Lambda for async worker path while keeping API on ECS.

## Decision Framework

### Option Scoring

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| **A** | **9.6** | **9.5** | **9.5** | **9.0** | **9.48** |
| B | 9.0 | 9.0 | 8.4 | 9.2 | 8.88 |
| C | 9.1 | 8.9 | 8.7 | 9.1 | 8.94 |

`weighted total = (leverage * 0.35) + (value * 0.30) + (maintenance * 0.25) + (adaptability * 0.10)`

## Decision

Choose Option A: preserve ECS/Fargate plus SQS runtime scope and exclude
Lambda orchestration in this release.

Implementation commitments:

- No Lambda or Step Functions components will be introduced for request,
  enqueue, worker processing, or worker result-update runtime paths.
- CI/CD may use AWS managed services, but runtime compute remains ECS task
  based with SQS async orchestration.
- Any future Lambda introduction requires a new ADR with migration, rollback,
  and observability parity plans.

## Related Requirements

- [FR-0001](../requirements.md#fr-0001-async-job-endpoints-and-orchestration)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
- [IR-0001](../requirements.md#ir-0001-sidecar-routing-model)
- [IR-0002](../requirements.md#ir-0002-aws-service-dependencies)

## Consequences

1. Positive outcomes: runtime behavior stays aligned with validated contracts,
   existing incident runbooks, and current observability model.
2. Trade-offs/costs: event-driven elasticity options available in Lambda are
   deferred until post-cutover with explicit re-evaluation.
3. Ongoing considerations: architecture evolution remains possible, but changes
   must be deliberate and ADR-governed to avoid incremental entropy.

## Changelog

- 2026-02-24: Initial ADR acceptance and implementation.
- 2026-02-24: Expanded to full template structure with explicit scoring and
  requirements traceability.

---

## ADR Completion Checklist

- [x] All placeholders (`<…>`) and bracketed guidance are removed/replaced.
- [x] All links are markdown-clickable and resolve to valid local docs or
  sources.
- [x] Context includes concrete constraints, not generic boilerplate.
- [x] Alternatives are decision-relevant and scored consistently.
- [x] Winning row is bold and matches the Decision section.
- [x] Accepted/Implemented ADR score is `>= 9.0`.
- [x] Related requirements link to exact requirement anchors.
- [x] Consequences include both benefits and trade-offs.
