---
ADR: 0015
Title: Nova API platform final hosting and deployment architecture (2026)
Status: Accepted
Version: 1.1
Date: 2026-03-02
Related:
  - "[ADR-0011: Hybrid CI/CD with GitHub and AWS promotion](./ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[ADR-0012: Preserve ECS and SQS runtime scope](./ADR-0012-no-lambda-runtime-scope.md)"
  - "[SPEC-0015: Nova API platform final topology and delivery contract](../spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md)"
References:
  - "[Amazon ECS Express Mode overview](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html)"
  - "[Best practices for Amazon ECS Express Mode services](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-best-practices.html)"
  - "[Amazon ECS deployment circuit breaker](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html)"
  - "[Optimize load balancer health checks for ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/load-balancer-healthcheck.html)"
---

## Summary

Adopt **standard ECS on Fargate with ALB + GitHub Actions OIDC and Nova-owned
deployment stacks** as the Nova API production final-state architecture.
Implementation is planned for the next feature branch and is not yet fully
delivered in runtime code.

## Context

Nova already converged toward ECS/Fargate and single-repo authority goals during the 30-day consolidation plan. A 2026 reassessment was required because ECS Express Mode is now generally available and materially changes the option set.

## Alternatives and scored decision

### Criteria and weights

- Security/compliance: 25%
- Reliability/rollback behavior: 20%
- Cost and right-sizing: 15%
- Operational simplicity: 15%
- Observability and auditability: 10%
- IaC maturity and governance: 10%
- FastAPI + worker + CodeArtifact fit: 5%

### Option scores

| Option | Weighted score (/10) |
| --- | ---: |
| A. ECS Express Mode on Fargate | 8.8 |
| B. Standard ECS/Fargate + ALB + CodeDeploy blue/green | **9.3** |
| C. EKS | 7.6 |
| D. App Runner | 8.1 |

Threshold policy: only options >=9.0 are accepted.

## Decision

Choose **Option B** as production final-state.

### Required characteristics

1. ECS/Fargate API service behind ALB.
2. Separate ECS/Fargate worker services with SQS orchestration.
3. Alarm-driven rollback controls with deployment circuit-breaker semantics.
4. GitHub Actions with OIDC AWS auth; no long-lived keys.
5. One-repo IaC authority in `nova` for runtime/deployment path.

## Consequences

### Positive

- Mature deployment control and rollback semantics.
- Strong compliance and audit chain (CloudTrail, CodeDeploy events, IAM boundaries).
- Excellent fit for FastAPI API + async worker split.

### Trade-offs

- Slightly more operational surface area than Express Mode-only usage.
- Requires explicit IaC modules for deploy groups, alarms, and policy hardening.

## Explicit non-decisions

- No EKS adoption for Nova runtime scope.
- No App Runner-only platform authority.
- No compatibility shims/wrappers for transitional runtime paths.

## Changelog

- 2026-03-01: Accepted final production hosting/deployment architecture after 2026 options re-evaluation.
- 2026-03-02: Clarified that the decision is accepted but implementation is
  planned and tracked in `SPEC-0015`.
