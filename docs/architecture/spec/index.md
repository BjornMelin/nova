# Architecture specifications

Status: Active index
Last reviewed: 2026-03-25

## Status model

- **Implemented** -- reflected in the current repository and current runbooks
- **Accepted, planned** -- approved target-state spec for wave-2 implementation
- **Superseded** -- historical / traceability only

## Current implemented baseline

| SPEC | Title | Decision status | Implementation state | Date |
| --- | --- | --- | --- | --- |
| [SPEC-0000](./SPEC-0000-http-api-contract.md) | HTTP API Contract | Active | Implemented baseline | 2026-03-03 |
| [SPEC-0001](./SPEC-0001-security-model.md) | Security Model | Active | Implemented baseline | 2026-03-03 |
| [SPEC-0002](./SPEC-0002-s3-integration.md) | S3 Integration | Active | Implemented baseline | 2026-02-11 |
| [SPEC-0003](./SPEC-0003-observability.md) | Observability | Active | Implemented baseline | 2026-03-03 |
| [SPEC-0004](./SPEC-0004-ci-cd-and-docs.md) | CI/CD and Documentation Automation | Active | Implemented baseline | 2026-03-03 |
| [SPEC-0005](./SPEC-0005-abuse-prevention-and-quotas.md) | Abuse Prevention and Quotas | Active | Implemented baseline | 2026-03-03 |
| [SPEC-0006](./SPEC-0006-jwt-oidc-verification-and-principal-mapping.md) | JWT/OIDC Verification and Principal Mapping | Active | Implemented baseline | 2026-02-12 |
| [SPEC-0008](./SPEC-0008-async-jobs-and-worker-orchestration.md) | Async Jobs and Worker Orchestration | Active | Implemented baseline | 2026-03-03 |
| [SPEC-0009](./SPEC-0009-caching-and-idempotency.md) | Caching and Idempotency | Active | Implemented baseline | 2026-02-13 |
| [SPEC-0010](./SPEC-0010-observability-analytics-and-activity-rollups.md) | Observability Analytics and Activity Rollups | Active | Implemented baseline | 2026-02-13 |
| [SPEC-0012](./SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md) | SDK Conformance, Versioning, and Compatibility Governance | Active | Implemented baseline | 2026-02-14 |
| [SPEC-0015](./SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md) | Nova API platform final topology and delivery contract | Active | Implemented baseline | 2026-03-03 |
| [SPEC-0016](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md) | V1 route namespace and literal guardrails | Active | Implemented baseline | 2026-03-03 |
| [SPEC-0017](./SPEC-0017-runtime-component-topology-and-ownership-contract.md) | Runtime component topology and ownership contract | Active | Implemented baseline | 2026-03-05 |
| [SPEC-0018](./SPEC-0018-runtime-configuration-and-startup-validation-contract.md) | Runtime configuration and startup validation contract | Active | Implemented baseline | 2026-03-05 |
| [SPEC-0019](./SPEC-0019-auth-execution-and-threadpool-safety-contract.md) | Auth execution and threadpool safety contract | Active | Implemented baseline | 2026-03-05 |
| [SPEC-0020](./SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md) | Architecture authority pack and documentation synchronization contract | Active | Implemented baseline | 2026-03-05 |
| [SPEC-0021](./SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md) | Downstream hard-cut integration and consumer validation contract | Active | Implemented baseline | 2026-03-04 |
| [SPEC-0022](./SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md) | Auth0 tenant ops reusable workflow contract | Active | Implemented baseline | 2026-03-04 |
| [SPEC-0023](./SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md) | SSM runtime base URL contract for deploy validation | Active | Implemented baseline | 2026-03-04 |
| [SPEC-0024](./SPEC-0024-cloudformation-module-contract.md) | CloudFormation module contract | Active | Implemented baseline | 2026-03-05 |
| [SPEC-0025](./SPEC-0025-reusable-workflow-integration-contract.md) | Reusable workflow integration contract | Active | Implemented baseline | 2026-03-05 |
| [SPEC-0026](./SPEC-0026-ci-cd-iam-least-privilege-matrix.md) | CI/CD IAM least-privilege matrix | Active | Implemented baseline | 2026-03-05 |

## Approved target-state program

| SPEC | Title | Decision status | Implementation state | Date |
| --- | --- | --- | --- | --- |
| [SPEC-0027](./SPEC-0027-public-api-v2.md) | Public API v2 | Accepted | Planned target | 2026-03-25 |
| [SPEC-0028](./SPEC-0028-export-workflow-state-machine.md) | Export workflow state machine | Accepted | Planned target | 2026-03-25 |
| [SPEC-0029](./SPEC-0029-platform-serverless.md) | Canonical serverless platform | Accepted | Planned target | 2026-03-25 |
| [SPEC-0030](./SPEC-0030-sdk-generation-and-package-layout.md) | SDK generation and package layout | Accepted | Planned target | 2026-03-25 |
| [SPEC-0031](./SPEC-0031-docs-and-tests-authority-reset.md) | Docs and tests authority reset | Accepted | Applied to docs pack / code still planned | 2026-03-25 |

## Superseded

Use `./superseded/` for traceability only. This includes the former wave-1
target-state specs that were replaced before implementation.
