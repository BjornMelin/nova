# Nova Architecture Authority Map

Status: Active
Last reviewed: 2026-03-24

## Purpose

This document routes readers to the correct architecture authority without
duplicating the full ADR and SPEC catalogs across top-level docs.
Other routers should point here rather than re-listing partial authority packs
or route-chain fragments.

**Active-only lists:** Sections below name **in-force** ADRs and SPECs only.
Superseded predecessors are **not** linked here (to avoid agents or readers
treating retired docs as current). Find them under `adr/index.md` and
`spec/index.md` (Superseded tables) and in `adr/superseded/` and
`spec/superseded/` for traceability.

## Canonical Runtime Contract Chain

Use this chain first for public runtime contract questions:

1. `requirements.md`
2. `adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
3. `spec/SPEC-0000-http-api-contract.md`
4. `spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
5. `spec/SPEC-0027-public-http-contract-revision-and-bearer-auth.md` (auth and
   OpenAPI revision; path namespace remains `/v1/*`)

Program router: `../plan/greenfield-simplification-program.md` and
`../plan/greenfield-authority-map.md`.

## Active Authority Packs

### Runtime API and route authority

Use when the question is about public routes, route literals, endpoint shapes,
or removed legacy namespaces.

- `requirements.md`
- `adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `spec/SPEC-0000-http-api-contract.md`
- `spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md`
- `spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `spec/SPEC-0027-public-http-contract-revision-and-bearer-auth.md`
- `spec/SPEC-0028-worker-job-lifecycle-and-direct-result-path.md`

### Green-field simplification authority

Use for target-state cuts: single runtime auth, bearer-only public contract,
direct worker persistence, native OpenAPI, shared outer-ASGI request context
plus shared FastAPI exception registration, async-first
`nova_file_api.public`, per-language SDK stacks, AWS composite platform, repo
rebaseline.

- `../plan/greenfield-simplification-program.md`
- `adr/ADR-0033-single-runtime-auth-authority.md` through
  `adr/ADR-0041-shared-pure-asgi-middleware-and-errors.md` (see
  `adr/index.md` for the full table)
- `spec/SPEC-0029-sdk-architecture-and-artifact-contract.md`

### Runtime topology, ownership, and safety authority

Use when the question is about package boundaries, startup validation, auth
execution, threadpool safety, or documentation synchronization.

Integration boundary: `nova_dash_bridge` consumes `nova_file_api.public` as the
canonical in-process transfer seam.

`nova_file_api.public` is async-first. FastAPI hosts should await that surface
directly, while explicit sync adapters remain only for sync-only framework
edges such as Flask/Dash.

Cross-cutting FastAPI transport authority now lives in
`packages/nova_runtime_support`: `RequestContextASGIMiddleware`,
`RequestContextFastAPI`, and `register_fastapi_exception_handlers`. Service
packages keep only thin domain-error adapters and app assembly.

- `adr/ADR-0024-layered-architecture-authority-pack.md`
- `adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md`
- `adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md`
- `spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md`
- `spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md`
- `spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md`
- `spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md`

Generated runtime-config matrix:

- `../release/runtime-config-contract.generated.md` is the operator-facing
  artifact generated from the canonical runtime settings contract. It documents
  current env vars, `ENV_VARS_JSON` support, and ECS template wiring without
  becoming an independent authority.

### Downstream validation authority

Use when the question is about cross-repo integration, Auth0 tenant workflows,
or deploy-validation base URL authority.

- `adr/ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md`
- `adr/ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md`
- `adr/ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md`
- `spec/SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md`
- `spec/SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md`
- `spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md`

### SDK and release-artifact governance authority

Use when the question is about public Python SDK topology, release-grade
TypeScript, or first-class internal R release artifacts.

- `adr/ADR-0038-sdk-architecture-by-language.md`
- `spec/SPEC-0029-sdk-architecture-and-artifact-contract.md`
- `spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`

### Adjacent deploy-governance authority

Use when the question is about CloudFormation module boundaries, reusable
workflows, CI/CD IAM policy, or deployment-control-plane design.

Current deploy-governance baseline: the ECS service runtime stack owns the
repo-managed task role and cache-secret execution-role policy, while the deploy
operator resolves the ECS infrastructure role from the Nova IAM control-plane
stack. Operator docs and workflows must not reintroduce external
`ECS_INFRASTRUCTURE_ROLE_ARN`, `TaskRole`, or generic execution-secret override
inputs.

- `adr/ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md`
- `adr/ADR-0039-aws-target-platform.md`
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
