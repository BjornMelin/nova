---
ADR: 0022
Title: Codify release validation read access in Nova IaC
Status: Accepted
Version: 1.0
Date: 2026-03-02
Related:
  - "[ADR-0011: Hybrid CI/CD with GitHub and AWS promotion](./ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](./ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
References:
  - "[AWS IAM policies and permissions boundaries](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html)"
  - "[Amazon ECS infrastructure IAM role for load balancers](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AmazonECSInfrastructureRolePolicyForLoadBalancers.html)"
---

## Summary

Adopt a dedicated release validation read role in Nova IaC using minimally scoped
read permissions from CodeConnections, CodePipeline, ECS/ELB/WAF, and runtime
infrastructure IAM surfaces.

## Context

Validation runs were blocked by denied IAM actions from the current operator
context. The target-state read surface now centers on:

- `codeconnections:GetConnection`
- `codepipeline:ListPipelineExecutions`
- `codepipeline:ListPipelines`
- `wafv2:GetWebACLForResource`

Nova required a reproducible, auditable, least-privilege path in-repo
(final-state) instead of ad-hoc/manual grants.

## Decision drivers (weighted)

- Reproducibility (0.40)
- Least privilege + explicit scope (0.30)
- Operational simplicity / low entropy (0.20)
- Auditability (0.10)

## Options considered

1. **Inline release validation read policy in `infra/nova/nova-iam-roles.yml` on a dedicated role (conditional creation by trusted principal ARN parameter)**
1. Standalone managed policy + separate role attachment choreography
1. Continue manual/operator-side IAM updates out-of-band

## Scoring

| Option | Repro (0.40) | Least Priv (0.30) | Simplicity (0.20) | Audit (0.10) | Weighted score |
| --- | --- | --- | --- | --- | --- |
| 1 | 9.7 | 9.2 | 9.3 | 9.6 | **9.44** |
| 2 | 9.0 | 9.0 | 8.4 | 9.4 | 8.92 |
| 3 | 3.0 | 4.0 | 6.0 | 2.0 | 3.90 |

Only Option 1 reaches the required >=9.0 threshold.

## Consensus pass

A `zen.consensus` pass was executed with multi-model roster (`openai/gpt-5.2`, `google/gemini-3.1-pro-preview`, `x-ai/grok-4.1-fast`).
The first returned perspective aligned with codifying the access in IaC and reinforced boundary/least-privilege posture. Due MCP server thread persistence limitations in this environment, the continuation thread could not be resumed for subsequent model turns. Final decision remains anchored to weighted scoring and primary AWS authorization docs below.

## AWS authorization references used

- AWS Service Authorization Reference -- CodeConnections
- AWS Service Authorization Reference -- CodePipeline
- AWS Service Authorization Reference -- AWS WAFV2
- AWS Service Authorization Reference -- IAM

Key implications used in policy design:

- `codeconnections:GetConnection` supports connection ARN scoping.
- `codepipeline:ListPipelineExecutions` supports pipeline ARN scoping.
- `codepipeline:ListPipelines` is list-level and requires `Resource: "*"`.
- `wafv2:ListWebACLs` is list-level and requires `Resource: "*"`.
- `iam:GetRole` scopes to the explicit ECS infrastructure role ARN.

## Decision

Adopt **Option 1**: codify a dedicated release validation read role in `infra/nova/nova-iam-roles.yml`, created when `ReleaseValidationTrustedPrincipalArn` is provided.

Policy stance:

- Scope to explicit ARNs where service supports it (`codeconnections:GetConnection`, pipeline-scoped reads).
- Use `Resource: "*"` only where service authorization model requires it (`ListPipelines`, `ListApplications`, selected runtime read APIs).
- Keep conceptual/config surface minimal: single role + single inline policy + one principal parameter.

## Consequences

Positive:

- Deterministic and reviewable in PRs.
- Removes manual IAM drift for release gate execution.
- Keeps implementation focused and minimal.

Tradeoffs:

- Requires setting `ReleaseValidationTrustedPrincipalArn` at stack deploy/update time.
- Some actions remain `*` scoped due AWS service authorization constraints.

## Implementation summary

- Added `ReleaseValidationTrustedPrincipalArn` parameter.
- Added `ReleaseValidationReadRole` with inline read-only release validation policy.
- Added conditional output `ReleaseValidationReadRoleArn`.
- Updated runbooks with apply/verify/rollback and evidence expectations.
