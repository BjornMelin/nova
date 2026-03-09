---
ADR: 0026
Title: OIDC and IAM role partitioning for deploy automation
Status: Accepted
Version: 1.1
Date: 2026-03-03
Related:
  - "[ADR-0011: Hybrid CI/CD with GitHub CI and AWS-native Dev to Prod promotion](./ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[SPEC-0019: CI/CD IAM least-privilege and role-boundary contract](../spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md)"
  - "[SPEC-0020: Rollout and validation strategy](../spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md)"
---

## Summary

Deploy automation uses partitioned IAM roles with GitHub OIDC as the entry
boundary, scoped pass-role controls, and environment-specific execution roles.

## Context

Live stack updates and promotion flows require role assumption and controlled
pass-role capabilities. Shared broad permissions increased rollback risk and
made incident recovery harder to reason about.

## Alternatives and scored decision

### Criteria and weights

- Solution leverage: 35%
- Application value: 30%
- Maintenance and cognitive load: 25%
- Architectural adaptability: 10%

### Option scores

| Option | Weighted score (/10) |
| --- | ---: |
| A. Single broad deploy role for all automation | 7.0 |
| B. Partition OIDC caller, CFN execution, and pipeline roles with scoped pass-role conditions | **9.4** |
| C. Use long-lived IAM user credentials in CI | 3.2 |

Threshold policy: only options >=9.0 are accepted.

## Decision

Choose **Option B**.

### Required characteristics

1. GitHub workflows assume a dedicated deploy role through OIDC.
2. CloudFormation execution roles are separate from caller role and environment
   scoped.
3. `iam:PassRole` is constrained to approved role ARNs and
   `iam:PassedToService` conditions.
4. Pipeline/service roles are separate from workflow caller roles.
5. IAM policy contracts are testable and enforced by infra guardrails.

## Consequences

### Positive

- Stronger least-privilege posture and clearer blast-radius boundaries.
- Better auditability of who can mutate each CI/CD control-plane role.
- Safer recovery path during stack rollback or drift remediation.

### Trade-offs

- Additional role/policy contract maintenance overhead.
- Recovery operations can block if account-level IAM grants are incomplete.

## Explicit non-decisions

- No reliance on static AWS keys in GitHub workflows.
- No wildcard pass-role permissions for deployment automation.

## Changelog

- 2026-03-03: Updated ADR scope to OIDC/IAM role partitioning for deploy automation.
