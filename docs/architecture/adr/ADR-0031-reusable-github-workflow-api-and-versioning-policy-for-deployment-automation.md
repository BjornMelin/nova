---
ADR: 0031
Title: Reusable GitHub workflow API and versioning policy for deployment automation
Status: Accepted
Version: 1.2
Date: 2026-03-09
Supersedes:
  - "ADR-0025"
Related:
  - "[ADR-0025: Reusable GitHub workflow API and versioning policy for deployment automation (superseded)](./superseded/ADR-0025-reusable-workflow-api-and-versioning-policy.md)"
  - "[ADR-0011: Hybrid CI/CD with GitHub CI and AWS-native Dev to Prod promotion](./ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[SPEC-0025: Reusable workflow integration contract](../spec/SPEC-0025-reusable-workflow-integration-contract.md)"
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

This ADR supersedes ADR-0025 as the active governance authority for reusable
workflow API and versioning policy.

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
