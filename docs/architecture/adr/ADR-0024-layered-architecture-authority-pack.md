---
ADR: 0024
Title: Layered operator authority pack for the Nova monorepo
Status: Accepted
Version: 2.0
Date: 2026-03-05
Related:
  - "[AGENTS.md runtime authority](../../../AGENTS.md)"
  - "[README.md runtime authority summary](../../../README.md)"
  - "[PRD authority baseline](../../PRD.md)"
  - "[Architecture requirements baseline](../requirements.md)"
  - "[Plan index authority set](../../plan/PLAN.md)"
  - "[Runbooks authority index](../../runbooks/README.md)"
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[ADR-0013: Public Python/TypeScript SDK topology uses generated contract-core clients and defers R productization](./ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md)"
  - "[ADR-0026: OIDC and IAM role partitioning for deploy automation](./ADR-0026-oidc-iam-role-partitioning-for-deploy-automation.md)"
  - "[ADR-0030: Native-CFN modular stack architecture for Nova infrastructure productization](./ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md)"
  - "[SPEC-0011: Public Python/TypeScript SDK architecture and deferred R package map](../spec/SPEC-0011-multi-language-sdk-architecture-and-package-map.md)"
  - "[SPEC-0012: Public SDK conformance, versioning, and compatibility governance](../spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)"
  - "[SPEC-0017: CloudFormation module contract](../spec/SPEC-0017-cloudformation-module-contract.md)"
  - "[SPEC-0018: Reusable workflow integration contract](../spec/SPEC-0018-reusable-workflow-integration-contract.md)"
  - "[SPEC-0019: CI/CD IAM least-privilege and role-boundary contract](../spec/SPEC-0019-ci-cd-iam-least-privilege-and-role-boundary-contract.md)"
  - "[SPEC-0020: Architecture authority pack and documentation synchronization contract](../spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md)"
---

## Summary

Nova keeps one active operator authority graph. Runtime API authority, public
SDK governance, and deploy-validation/control-plane authority must each have a
truthful documented owner, and the same graph must appear in AGENTS, README,
PRD, plan, runbooks, and indexes.

## Context

Nova is greenfield and hard-cut by default. We do not preserve parallel
authority chains, stale paths, or misleading labels that imply a different
subject than the file actually governs.

## Alternatives and scored decision

### Criteria and weights

- Solution leverage: 35%
- Application value: 30%
- Maintenance and cognitive load: 25%
- Architectural adaptability: 10%

### Option scores

| Option | Weighted score (/10) |
| --- | ---: |
| A. Keep stale labels and broken links across active docs | 3.9 |
| B. Normalize the operator authority graph and make every active path truthful | **9.8** |
| C. Add more overlay docs while leaving the current drift in place | 5.4 |

Threshold policy: only options `>= 9.0` are accepted.

## Decision

Choose **Option B**.

### Required characteristics

1. Runtime API authority is anchored by `ADR-0023`, `SPEC-0000`,
   `SPEC-0015`, and `SPEC-0016`.
2. Public SDK governance is anchored by `ADR-0013`, `SPEC-0011`, and
   `SPEC-0012`.
3. Downstream/deploy-validation authority is anchored by `ADR-0027` through
   `ADR-0029` and `SPEC-0017` through `SPEC-0023`.
4. `ADR-0024` governs the layered boundaries and synchronization rules across
   those operator-facing documentation layers.
5. README, AGENTS, PRD, requirements, plan, runbooks, standards docs, and
   indexes must all reference the same operator authority graph in the same
   change.

## Consequences

### Positive

- Engineers can trust the active authority graph again.
- SDK governance becomes first-class instead of implicit.
- Deployment docs remain available without polluting runtime API authority.
- Review and test guardrails can key off one truthful active doc set.

### Trade-offs

- Existing cross-links and indexes require a one-time cleanup pass.
- Historical references that used stale filenames must be updated.

## Explicit non-decisions

- No duplicate active operator authority list.
- No stale link preservation inside active docs.
- No compatibility note that treats broken or misleading active paths as still
  valid.

## Changelog

- 2026-03-05: Restored `ADR-0024` as the runtime authority-pack decision and
  moved displaced deploy/workflow/IAM topics to new identifiers.
- 2026-03-09: Reframed `ADR-0024` as the layered operator authority decision
  and aligned the active graph with truthful runtime, SDK, and deploy-validation
  owners.
