---
ADR: 0016
Title: Minimal governance final-state operator path
Status: Superseded
Version: 1.0
Date: 2026-03-02
Related:
  - "[ADR-0011: Hybrid CI/CD with GitHub and AWS promotion](../ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[ADR-0014: container-craft absorption and repo retirement](./ADR-0014-container-craft-capability-absorption-and-repo-retirement.md)"
  - "[ADR-0015: Nova API platform final hosting and deployment architecture (2026)](../ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md)"
  - "[ADR-0030: Native-CFN modular stack architecture for Nova infrastructure productization](../ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md)"
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](../ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](../ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
  - "[Governance lock runbook](../../../plan/release/governance-lock-runbook.md)"
References:
  - "[GitHub branch protection API](https://docs.github.com/en/rest/branches/branch-protection?apiVersion=2022-11-28)"
  - "[About code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)"
---

This ADR is superseded and retained for historical traceability only.

## Summary

Adopt a **minimal governance final-state** for Nova operations: one canonical
ADR-backed governance decision artifact, concise CODEOWNERS coverage on authority
domains, and a short operator checklist/runbook path for lock verification and
execution.

## Context

Prior Track B execution landed in a non-canonical clone without remotes,
creating governance drift risk. The canonical `nova` repo needs one final,
auditable governance decision and a reduced operator path that preserves branch
protection rigor without duplicated procedural surface area.

## Alternatives and scored decision

### Criteria and weights

- Governance control strength: 30%
- Auditability and evidence quality: 20%
- Operator simplicity: 20%
- Drift resistance across repos/clones: 20%
- Documentation maintenance overhead: 10%

### Option scores

| Option | Weighted score (/10) |
| --- | ---: |
| A. Keep current multi-document governance process mostly unchanged | 8.4 |
| B. Minimal final-state governance path in canonical docs + concise ownership | **9.4** |
| C. Move governance execution to external reports-only artifacts | 7.1 |

Threshold policy: only options >=9.0 are accepted.

## Decision

Choose **Option B**.

### Required characteristics

1. Governance decision authority is recorded under `docs/architecture/adr/**`.
2. `.github/CODEOWNERS` remains concise and explicitly covers architecture,
   infra, contracts, and workflow authority domains.
3. Governance prep/checklist docs are reduced to a minimal operator flow with
   verification-first steps and explicit evidence capture.
4. No reports-only path is treated as operational governance authority.

## Consequences

### Positive

- Single canonical governance decision source in-repo.
- Lower cognitive load for operators while preserving controls.
- Reduced chance of divergence between planning and enforcement artifacts.

### Trade-offs

- Less narrative guidance for first-time operators.
- Requires disciplined linking from release docs to keep minimal path discoverable.

## Explicit non-decisions

- No additional transitional governance wrappers or parallel runbook stacks.
- No expansion of CODEOWNERS beyond authority-critical paths.
- No governance authority delegated to out-of-repo reports.

## Changelog

- 2026-03-02: Accepted as final-state Track B governance decision in canonical `nova` repository.
