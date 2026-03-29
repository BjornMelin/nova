---
ADR: 0014
Title: Absorb remaining container-craft Nova capabilities into nova and retire container-craft
Status: Superseded
Version: 1.0
Date: 2026-02-28
Superseded-by: "[ADR-0024: Layered runtime authority pack for the Nova monorepo](../ADR-0024-layered-architecture-authority-pack.md)"
Related:
  - "[ADR-0011: Hybrid CI/CD with GitHub and AWS promotion](../ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[ADR-0012: No Lambda runtime scope](./ADR-0012-no-lambda-runtime-scope.md)"
  - "[ADR-0015: Nova API platform final hosting and deployment architecture (2026)](./ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md)"
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](../ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[ADR-0024: Layered runtime authority pack for the Nova monorepo](../ADR-0024-layered-architecture-authority-pack.md)"
  - "[ADR-0025: Reusable GitHub workflow API and versioning policy (superseded predecessor)](./ADR-0025-reusable-workflow-api-and-versioning-policy.md)"
  - "[ADR-0026: OIDC and IAM role partitioning for deploy automation (superseded predecessor)](./ADR-0026-oidc-iam-role-partitioning-for-deploy-automation.md)"
  - "[ADR-0030: Native-CFN modular stack architecture for Nova infrastructure productization](../ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md)"
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](../ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](../ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
  - "[SPEC-0004: CI/CD and documentation automation](../../spec/SPEC-0004-ci-cd-and-docs.md)"
  - "[SPEC-0013: Container-craft capability absorption execution spec (superseded)](../../spec/superseded/SPEC-0013-container-craft-capability-absorption-execution-spec.md)"
  - "[SPEC-0014: Container-craft capability inventory and Nova absorption target map (superseded)](../../spec/superseded/SPEC-0014-container-craft-capability-inventory-and-absorption-map.md)"
References:
  - "[AWS CodePipeline: how executions work (multiple source actions behavior)](https://docs.aws.amazon.com/codepipeline/latest/userguide/concepts-how-it-works.html)"
  - "[AWS CodePipeline CloudFormation action reference](https://docs.aws.amazon.com/codepipeline/latest/userguide/action-reference-CloudFormation.html)"
  - "[AWS CodePipeline source actions and change detection](https://docs.aws.amazon.com/codepipeline/latest/userguide/change-detection-methods.html)"
---

This ADR is superseded and retained for historical traceability only.

## Summary

Adopt full final-state absorption of all Nova-required capabilities still living in `container-craft` into the `nova` monorepo, then archive/delete `container-craft` once hard readiness gates are met.

## Context

Current state still has release-path authority split across repos:

- Runtime app/release logic is now primarily in `nova`.
- Core AWS promotion IaC for Nova (`infra/nova/*.yml` and `infra/nova/deploy/image-digest-ssm.yml`) remains in `container-craft` and is consumed via `InfraSourceOutput` dual-source CodePipeline behavior.
- This creates two-repo coupling for one production release path and violates final-state single-ownership intent.

Additional discovery:

- `container-craft` still contains broad generic deploy modes (`deploy-ecs`, `deploy-ecr`, `deploy-kms`, etc.) and renderer logic that are out of scope for Nova’s final runtime model.
- Nova already has replacement release workflows/buildspecs/runbooks for most CI/release logic; the main missing capability class is AWS promotion IaC ownership in-repo.

## Alternatives (adversarial scoring)

### Scoring dimensions and weights

- Security boundary clarity (25%)
- Operational reliability and auditability (25%)
- Entropy reduction / cognitive load (20%)
- Delivery risk during migration (15%)
- Long-term maintainability (15%)

### Option scoring

| Option | Security | Reliability | Entropy reduction | Delivery risk | Maintainability | Weighted total (/10) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A. Keep split authority (nova + container-craft long-term) | 8.1 | 8.0 | 6.9 | 8.8 | 7.2 | 7.79 |
| B. Full absorption into nova; retire container-craft for Nova path | 9.5 | 9.4 | 9.8 | 8.9 | 9.6 | **9.45** |
| C. Partial absorption; keep container-craft for IaC-only Nova deploys | 8.9 | 8.8 | 8.4 | 8.9 | 8.7 | 8.75 |

`weighted = security*0.25 + reliability*0.25 + entropy*0.20 + risk*0.15 + maintainability*0.15`

## Retained options (>= 9.0 only)

- **Option B only (9.45/10)**.

## Decision

Choose **Option B**:

1. Move Nova promotion IaC templates from `container-craft/infra/nova/**` into `nova/infra/nova/**`.
2. Refactor pipeline template to single-repo source model (only `AppSourceOutput`) for final state.
3. Update release and deployment docs/contracts to remove references to container-craft as active infra authority.
4. Enforce archive/delete hard gates (defined in SPEC-0013) before repository retirement.

## Consequences

### Positive

- Single repository owns Nova build, release, and promotion semantics.
- Elimination of `InfraSourceOutput` dual-source drift class.
- Cleaner audit chain and lower operator confusion.

### Trade-offs

- Requires one careful migration window to shift template paths and CloudFormation stack updates.
- Requires strict regression tests for IAM, CodePipeline source/deploy wiring, and runbooks.

### Non-goals

- No transitional wrappers/shims.
- No new generic deployment framework work inside Nova beyond what Nova needs.

## Readiness and retirement policy

`container-craft` may be archived/deleted for Nova usage only when all are true:

1. Nova owns all production-relevant Nova IaC templates and references.
2. Pipeline uses single-source Nova repo for app + infra pathing.
3. Dev and Prod promotion runs complete with immutable digest and post-deploy validation evidence.
4. All SPEC-0013 acceptance tests pass in CI.
5. Docs/runbooks are updated and no active instructions require container-craft for Nova releases.

## Changelog

- 2026-02-28: Initial acceptance for full capability absorption and repo retirement criteria.
