---
ADR: 0024
Title: Layered runtime authority pack for the Nova monorepo
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
  - "[ADR-0025: Runtime monorepo component boundaries and ownership](./ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md)"
  - "[ADR-0026: Fail-fast runtime configuration and safe auth execution](./ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)"
  - "[ADR-0030: Native-CFN modular stack architecture for Nova infrastructure productization](./ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md)"
  - "[SPEC-0017: Runtime component topology and ownership contract](../spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md)"
  - "[SPEC-0018: Runtime configuration and startup validation contract](../spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md)"
  - "[SPEC-0019: Auth execution and threadpool safety contract](../spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md)"
  - "[SPEC-0020: Architecture authority pack and documentation synchronization contract](../spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md)"
---

## Summary

Nova keeps one active runtime authority pack. The active runtime ADR/SPEC set
must describe runtime package boundaries, runtime configuration rules, and auth
execution safety. Deployment-control-plane, reusable workflow, and CI/CD IAM
subjects are governed separately and must not occupy runtime authority IDs.

## Context

Nova is greenfield and hard-cut by default. We do not preserve parallel
authority chains or tolerate mixed runtime/deploy topics inside the same active
identifier set.

## Alternatives and scored decision

### Criteria and weights

- Solution leverage: 35%
- Application value: 30%
- Maintenance and cognitive load: 25%
- Architectural adaptability: 10%

### Option scores

| Option | Weighted score (/10) |
| --- | ---: |
| A. Keep current identifiers but tolerate mixed runtime and deploy subjects | 4.7 |
| B. Restore runtime subjects to the active identifiers and move deploy/workflow/IAM content to new identifiers | **9.8** |
| C. Create a second active authority list for runtime while leaving the current files untouched | 5.6 |

Threshold policy: only options `>= 9.0` are accepted.

## Decision

Choose **Option B**.

### Required characteristics

1. The active runtime authority pack is:
   - `ADR-0023`, `ADR-0024`, and `ADR-0027` through `ADR-0029`
   - `SPEC-0000`, `SPEC-0015`, `SPEC-0016`, and `SPEC-0017` through `SPEC-0023`
2. `ADR-0024` governs layered authority-pack boundaries for runtime
   documentation subjects.
3. `SPEC-0017` through `SPEC-0023` govern runtime topology,
   configuration/startup validation, auth/threadpool safety, downstream
   integration contracts, Auth0 reusable workflow contracts, and SSM base-url
   authority.
4. Infrastructure productization, reusable workflow API governance, and CI/CD
   IAM least-privilege move to `ADR-0030` through `ADR-0032` and
   `SPEC-0024` through `SPEC-0026`.
5. README, AGENTS, PRD, requirements, plan, runbooks, and indexes must all
   reference the same authority graph in the same change.

## Consequences

### Positive

- Runtime engineers can trust the active authority IDs again.
- Deployment docs remain available without polluting runtime authority.
- Review and test guardrails can key off one truthful active doc set.

### Trade-offs

- Existing cross-links and indexes require a one-time renumbering pass.
- Historical references that used the drifted subject mapping must be updated.

## Explicit non-decisions

- No duplicate active runtime authority list.
- No mixed runtime/deployment subject matter inside one active identifier.
- No compatibility note that treats the drifted identifiers as still valid for
  deploy/workflow/IAM governance.

## Changelog

- 2026-03-05: Restored `ADR-0024` as the runtime authority-pack decision and
  moved displaced deploy/workflow/IAM topics to new identifiers.
