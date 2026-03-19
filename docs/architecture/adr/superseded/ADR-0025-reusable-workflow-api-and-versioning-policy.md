---
ADR: 0025
Title: Reusable GitHub workflow API and versioning policy for deployment automation
Status: Superseded
Version: 1.2
Date: 2026-03-09
Superseded-by: "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](../ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
Related:
  - "[requirements.md](../../requirements.md)"
  - "[ADR-0023: Hard-cut v1 canonical route surface](../ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API contract](../../spec/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: Hard-cut v1 route contract and route-literal guardrails](../../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[ADR-0011: Hybrid CI/CD with GitHub CI and AWS-native Dev to Prod promotion](../ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[SPEC-0018: Reusable workflow integration contract](../../spec/superseded/SPEC-0018-reusable-workflow-integration-contract.md)"
  - "[SPEC-0004: CI/CD and documentation automation](../../spec/SPEC-0004-ci-cd-and-docs.md)"
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](../ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
---

## Summary

Nova publishes reusable `workflow_call` deployment APIs as a product contract.
Entry workflows become thin wrappers, and downstream repos consume stable
versioned workflow interfaces.

## Context

Deployment logic was duplicated across workflow entrypoints and difficult to
reuse from downstream repos. Contract drift risk increased because inputs,
outputs, and behavior were not consistently documented or versioned.

## Alternatives and scored decision

### Criteria and weights

- Solution leverage: 35%
- Application value: 30%
- Maintenance and cognitive load: 25%
- Architectural adaptability: 10%

### Option scores

| Option | Weighted score (/10) |
| --- | ---: |
| A. Keep only repository-local workflow_dispatch entrypoints | 7.1 |
| B. Publish typed reusable workflows with explicit contract schemas | **9.5** |
| C. Replace workflows with ad-hoc shell scripts per consumer repo | 6.8 |

Threshold policy: only options >=9.0 are accepted.

## Decision

Choose **Option B**.

### Required characteristics

1. Reusable workflow APIs are exposed via `workflow_call` and typed
   input/output contracts.
2. Shared behavior is encapsulated in composite actions under
   `.github/actions/**`.
3. Entry workflows in `.github/workflows/**` are wrappers around reusable
   implementations.
4. Versioning contract:
   - `@v1` is stable compatibility channel.
   - `@v1.x.y` tags are immutable release pins for production use.

## Consequences

### Positive

- Single implementation path for release/deploy/promote flows.
- Lower maintenance and reduced behavior skew across workflows.
- Consumer repos can integrate with minimal YAML and clear contracts.

### Trade-offs

- Requires stricter schema/doc synchronization discipline.
- Introduces explicit version lifecycle management for workflow APIs.

## Explicit non-decisions

- No unpublished or implicit workflow API behavior.
- No backward-compatibility shims outside declared `v1` contract rules.

## Changelog

- 2026-03-03: Updated ADR scope to reusable workflow API and versioning policy.
- 2026-03-09: Marked as superseded by ADR-0031.
