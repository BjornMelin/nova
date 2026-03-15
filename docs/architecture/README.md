# Nova Architecture Authority Map

Status: Active
Last reviewed: 2026-03-14

## Purpose

This document routes readers to the correct architecture authority without
duplicating the full ADR and SPEC catalogs across top-level docs.

## Canonical Runtime Contract Chain

Use this chain first for public runtime contract questions:

1. `requirements.md`
2. `adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
3. `spec/SPEC-0000-http-api-contract.md`
4. `spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`

## Active Authority Packs

### Runtime API and route authority

Use when the question is about public routes, route literals, endpoint shapes,
or removed legacy namespaces.

- `requirements.md`
- `adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `spec/SPEC-0000-http-api-contract.md`
- `spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md`
- `spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`

### Runtime topology, ownership, and safety authority

Use when the question is about package boundaries, startup validation, auth
execution, threadpool safety, or documentation synchronization.

Integration boundary: `nova_dash_bridge` consumes `nova_file_api.public` as the
canonical in-process transfer seam. Normative ownership and boundary rules are
defined in:

- `adr/ADR-0024-layered-architecture-authority-pack.md`
- `adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md`
- `adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md`
- `spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md`
- `spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md`
- `spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md`
- `spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md`

### Downstream validation authority

Use when the question is about cross-repo integration, Auth0 tenant workflows,
or deploy-validation base URL authority.

- `adr/ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md`
- `adr/ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md`
- `adr/ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md`
- `spec/SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md`
- `spec/SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md`
- `spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md`

### Adjacent deploy-governance authority

Use when the question is about CloudFormation module boundaries, reusable
workflows, CI/CD IAM policy, or deployment-control-plane design.

- `adr/ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md`
- `adr/ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md`
- `adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md`
- `adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md`
- `spec/SPEC-0024-cloudformation-module-contract.md`
- `spec/SPEC-0025-reusable-workflow-integration-contract.md`
- `spec/SPEC-0026-ci-cd-iam-least-privilege-matrix.md`

Quality-gate implementation details, including repo-local pre-commit hooks and
the canonical `ty` plus `mypy` typing-gate wiring, remain governed by
`../standards/README.md` and
do not replace the required gate authority in `requirements.md`.

## Catalog Indexes

Use these when you know the kind of architecture doc you need but not the exact
identifier:

- `adr/index.md`
- `spec/index.md`

## Historical Material

These are not active authority:

- `adr/superseded/`
- `spec/superseded/`
- `../history/`
