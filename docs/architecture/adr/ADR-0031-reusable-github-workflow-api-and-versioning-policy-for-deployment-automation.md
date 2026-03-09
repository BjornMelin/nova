---
ADR: 0031
Title: Reusable GitHub workflow API and versioning policy for deployment automation
Status: Accepted
Version: 1.0
Date: 2026-03-05
Related:
  - "[ADR-0011: Hybrid CI/CD with GitHub CI and AWS-native Dev to Prod promotion](./ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[SPEC-0025: Reusable workflow integration contract](../spec/SPEC-0025-reusable-workflow-integration-contract.md)"
  - "[SPEC-0004: CI/CD and documentation automation](../spec/SPEC-0004-ci-cd-and-docs.md)"
---

## Summary

Nova publishes reusable `workflow_call` deployment APIs as a product contract.
Entry workflows remain thin wrappers, and downstream repos consume stable,
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

Threshold policy: only options `>= 9.0` are accepted.

## Decision

Choose **Option B**.

### Required characteristics

1. Reusable workflow APIs are exposed via `workflow_call` and typed
   input/output contracts.
2. Shared behavior is encapsulated in composite actions under
   `.github/actions/**`.
3. Entry workflows in `.github/workflows/**` are wrappers around reusable
   implementations.
4. Reference contract:
   - reusable workflows remain typed `workflow_call` interfaces
   - moving major tags such as `@v1` and `@v2` are the published compatibility
     channels for cross-repo callers
   - immutable release tags such as `@v1.x.y` and full commit SHAs are also
     supported
   - production and high-assurance consumers pin immutable release tags or full
     commit SHAs
   - breaking caller-visible workflow changes require a new major tag rather
     than compatibility shims
   - composite actions remain internal implementation details, not direct
     external APIs

## Consequences

### Positive

- Single implementation path for release/deploy/promote flows.
- Lower maintenance and reduced behavior skew across workflows.
- Consumer repos can integrate with minimal YAML and clear contracts.

### Trade-offs

- Requires stricter schema/doc synchronization discipline.
- Introduces explicit version lifecycle management for workflow APIs.
- Requires release-tag governance so moving major tags track only compatible
  releases.

## Explicit non-decisions

- No unpublished or implicit workflow API behavior.
- No backward-compatibility shims outside declared `v1` contract rules.

## Changelog

- 2026-03-05: Reissued reusable workflow governance under `ADR-0031` after
  runtime authority identifiers were restored.
