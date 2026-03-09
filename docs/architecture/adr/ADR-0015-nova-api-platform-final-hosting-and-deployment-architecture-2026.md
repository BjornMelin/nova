---
ADR: 0015
Title: Nova API platform final hosting and deployment architecture (2026)
Status: Accepted
Version: 1.3
Date: 2026-03-03
Related:
  - "[ADR-0011: Hybrid CI/CD with GitHub and AWS promotion](./ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[ADR-0012: Preserve ECS and SQS runtime scope](./ADR-0012-no-lambda-runtime-scope.md)"
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0015: Nova API platform final topology and delivery contract](../spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md)"
  - "[SPEC-0016: v1 route namespace and literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
References:
  - "[Amazon ECS Express Mode overview](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html)"
  - "[Best practices for Amazon ECS Express Mode services](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-best-practices.html)"
  - "[Amazon ECS blue/green deployments](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-type-blue-green.html)"
  - "[AWS::ECS::Service DeploymentConfiguration](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-ecs-service-deploymentconfiguration.html)"
  - "[Amazon ECS infrastructure IAM role for load balancers](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AmazonECSInfrastructureRolePolicyForLoadBalancers.html)"
  - "[Optimize load balancer health checks for ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/load-balancer-healthcheck.html)"
---

## Summary

Adopt **standard ECS on Fargate with ALB + GitHub Actions OIDC and Nova-owned
deployment stacks using the ECS-native blue/green deployment strategy on
`AWS::ECS::Service`** as the Nova API production final-state architecture.
Route-surface authority is hard-cut canonical `/v1/*` (plus
`/metrics/summary`).

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
| B. Standard ECS/Fargate + ALB + ECS-native blue/green | **9.6** |
| C. EKS | 7.6 |
| D. App Runner | 8.1 |

Threshold policy: only options >=9.0 are accepted.

## Decision

Choose **Option B** as production final-state.

### Required characteristics

1. ECS/Fargate API service behind ALB.
2. Separate ECS/Fargate worker services with SQS orchestration.
3. ECS-native blue/green deployment with:
   - `DeploymentController.Type=ECS`
   - `DeploymentConfiguration.Strategy=BLUE_GREEN`
   - CloudWatch deployment alarms
   - load-balancer infrastructure role wiring
4. Public ALB paths use WAFv2 protection with rate-based controls for
   `/v1/transfers*` and `/v1/jobs*`.
5. GitHub Actions with OIDC AWS auth; no long-lived keys.
6. One-repo IaC authority in `nova` for runtime/deployment path.

## Consequences

### Positive

- Mature deployment control and rollback semantics.
- Strong compliance and audit chain (CloudTrail, ECS deployment events, IAM boundaries).
- Excellent fit for FastAPI API + async worker split.

### Trade-offs

- Slightly more operational surface area than Express Mode-only usage.
- Requires explicit IaC modules for target groups, listener rules, WAF, alarms,
  and policy hardening.

## Explicit non-decisions

- EKS will not be adopted for the Nova runtime scope.
- We will not designate App Runner as the sole platform authority.
- Compatibility shims/wrappers for transitional runtime paths will not be provided.

## Changelog

- 2026-03-01: Accepted final production hosting/deployment architecture after 2026 options re-evaluation.
- 2026-03-02: Clarified active implementation status and aligned to dual-track
  runtime authority during the transition window.
- 2026-03-03: Updated route authority to hard-cut canonical `/v1/*` via
  `ADR-0023` and `SPEC-0016`.
- 2026-03-05: Replaced CodeDeploy target-state wording with ECS-native
  blue/green deployment authority and WAF-backed public ingress.
