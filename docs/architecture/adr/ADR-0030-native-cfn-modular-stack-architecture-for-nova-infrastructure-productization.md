---
ADR: 0030
Title: Native-CFN modular stack architecture for Nova infrastructure productization
Status: Accepted
Version: 1.0
Date: 2026-03-05
Related:
  - "[ADR-0011: Hybrid CI/CD with GitHub CI and AWS-native Dev to Prod promotion](./ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[SPEC-0017: CloudFormation module contract](../spec/SPEC-0017-cloudformation-module-contract.md)"
  - "[SPEC-0020: Architecture authority pack and documentation synchronization contract](../spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md)"
  - "[SPEC-0004: CI/CD and documentation automation](../spec/SPEC-0004-ci-cd-and-docs.md)"
---

## Summary

Nova infrastructure is standardized on native CloudFormation templates only,
with explicit module boundaries and import/export contracts across foundation,
IAM, CodeBuild, CI/CD, runtime, and SSM authority stacks.

## Context

The productized deployment surface requires deterministic IaC for internal and
downstream consumers. Template rendering layers and mixed orchestration models
caused drift, made changes harder to review, and weakened cross-repo reuse.

## Alternatives and scored decision

### Criteria and weights

- Solution leverage: 35%
- Application value: 30%
- Maintenance and cognitive load: 25%
- Architectural adaptability: 10%

### Option scores

| Option | Weighted score (/10) |
| --- | ---: |
| A. Keep hybrid Jinja + CloudFormation rendering model | 6.9 |
| B. Adopt native CloudFormation modular stacks as canonical | **9.7** |
| C. Rewrite deployment control plane to custom scripts only | 7.4 |

Threshold policy: only options `>= 9.0` are accepted.

## Decision

Choose **Option B**.

### Required characteristics

1. Deployable templates in `infra/` must be valid native CloudFormation and
   must not contain Jinja control syntax.
2. Stack composition is module-based:
   - `nova-foundation.yml`
   - `nova-iam-roles.yml`
   - `nova-codebuild-release.yml`
   - `nova-ci-cd.yml`
   - `infra/nova/deploy/service-base-url-ssm.yml`
   - runtime templates under `infra/runtime/**`
3. Cross-stack dependencies use explicit exports/imports.
4. Change-set-first deployment is the default execution contract.

## Consequences

### Positive

- Deterministic IaC behavior across local CI and AWS live deploys.
- Clear ownership and review surfaces per stack module.
- Better compatibility for reusable workflow APIs consumed by other repos.

### Trade-offs

- Slightly higher explicit parameter/output contract maintenance.
- Existing live stacks may require one-time recovery from drifted states.

## Explicit non-decisions

- No template renderer compatibility layer.
- No hidden stack coupling via undocumented parameter side effects.

## Changelog

- 2026-03-05: Reissued infrastructure productization authority under `ADR-0030`
  after runtime authority identifiers were restored.
