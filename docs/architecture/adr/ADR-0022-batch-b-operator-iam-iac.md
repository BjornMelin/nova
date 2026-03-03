---
ADR: 0022
Title: Codify Batch B operator validation IAM access in Nova IaC
Status: Accepted
Version: 1.0
Date: 2026-03-02
Related:
  - "[ADR-0011: Hybrid CI/CD with GitHub and AWS promotion](./ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[ADR-0016: Minimal governance final-state operator path](./ADR-0016-minimal-governance-final-state-operator-path.md)"
References:
  - "[AWS IAM policies and permissions boundaries](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html)"
  - "[AWS CodeDeploy documentation](https://docs.aws.amazon.com/codedeploy/latest/userguide/getting-started.html)"
---

## Summary

Adopt a dedicated Batch B validation operator role in Nova IaC using minimally
scoped read permissions from CodeConnections, CodePipeline, and CodeDeploy, and
preserve release operators in one auditable path.

## Context

Batch B validation runs were blocked by denied IAM actions from the current operator context:

- `codeconnections:GetConnection`
- `codepipeline:ListPipelineExecutions`
- `codepipeline:ListPipelines`
- `codedeploy:ListApplications`

Nova required a reproducible, auditable, least-privilege path in-repo (final-state) instead of ad-hoc/manual grants.

## Decision drivers (weighted)

- Reproducibility (0.40)
- Least privilege + explicit scope (0.30)
- Operational simplicity / low entropy (0.20)
- Auditability (0.10)

## Options considered

1. **Inline Batch B validation policy in `infra/nova/nova-iam-roles.yml` on a dedicated operator role (conditional creation by principal ARN parameter)**
2. Standalone managed policy + separate role attachment choreography
3. Continue manual/operator-side IAM updates out-of-band

## Scoring

| Option | Repro (0.40) | Least Priv (0.30) | Simplicity (0.20) | Audit (0.10) | Weighted score |
|---|---:|---:|---:|---:|---:|
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
- AWS Service Authorization Reference -- CodeDeploy

Key implications used in policy design:

- `codeconnections:GetConnection` supports connection ARN scoping.
- `codepipeline:ListPipelineExecutions` supports pipeline ARN scoping.
- `codepipeline:ListPipelines` is list-level and requires `Resource: "*"`.
- `codedeploy:ListApplications` is list-level and requires `Resource: "*"`.

## Decision

Adopt **Option 1**: codify a dedicated Batch B validation operator role in `infra/nova/nova-iam-roles.yml`, created when `BatchBOperatorPrincipalArn` is provided.

Policy stance:

- Scope to explicit ARNs where service supports it (`codeconnections:GetConnection`, pipeline-scoped reads).
- Use `Resource: "*"` only where service authorization model requires it (`ListPipelines`, `ListApplications`, selected runtime read APIs).
- Keep conceptual/config surface minimal: single role + single inline policy + one principal parameter.

## Consequences

Positive:

- Deterministic and reviewable in PRs.
- Removes manual IAM drift for Batch B gate execution.
- Keeps implementation focused and minimal.

Tradeoffs:

- Requires setting `BatchBOperatorPrincipalArn` at stack deploy/update time.
- Some actions remain `*` scoped due AWS service authorization constraints.

## Implementation summary

- Added `BatchBOperatorPrincipalArn` parameter.
- Added `BatchBValidationOperatorRole` with inline read-only Batch B validation policy.
- Added conditional output `BatchBValidationOperatorRoleArn`.
- Updated runbooks with apply/verify/rollback and evidence expectations.
