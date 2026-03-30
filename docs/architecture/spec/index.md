# Architecture specifications

Status: Active index
Last reviewed: 2026-03-29

## Canonical architecture authority chain

- [ADR-0023](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)
- [SPEC-0016](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)
- [requirements.md](../requirements.md)

## Active canonical specs

| SPEC | Title | Decision status | Implementation state | Date |
| --- | --- | --- | --- | --- |
| [SPEC-0027](./SPEC-0027-public-api-v2.md) | Public API v2 | Accepted | Active baseline | 2026-03-25 |
| [SPEC-0028](./SPEC-0028-export-workflow-state-machine.md) | Export workflow state machine | Accepted | Active baseline | 2026-03-25 |
| [SPEC-0029](./SPEC-0029-platform-serverless.md) | Canonical serverless platform | Accepted | Active baseline | 2026-03-25 |
| [SPEC-0030](./SPEC-0030-sdk-generation-and-package-layout.md) | SDK generation and package layout | Accepted | Active baseline | 2026-03-25 |
| [SPEC-0031](./SPEC-0031-docs-and-tests-authority-reset.md) | Docs and tests authority reset | Accepted | Active baseline | 2026-03-25 |

## Active supporting specs

| SPEC | Title | Decision status | Implementation state | Date |
| --- | --- | --- | --- | --- |
| [SPEC-0001](./SPEC-0001-security-model.md) | Security Model | Active | Active supporting current-state doc | 2026-03-03 |
| [SPEC-0002](./SPEC-0002-s3-integration.md) | S3 Integration | Active | Active supporting current-state doc | 2026-02-11 |
| [SPEC-0003](./SPEC-0003-observability.md) | Observability | Active | Active supporting current-state doc | 2026-03-03 |
| [SPEC-0004](./SPEC-0004-ci-cd-and-docs.md) | CI/CD and Documentation Automation | Active | Active supporting current-state doc | 2026-03-24 |
| [SPEC-0005](./SPEC-0005-abuse-prevention-and-quotas.md) | Abuse Prevention and Quotas | Active | Active supporting current-state doc | 2026-03-11 |
| [SPEC-0006](./SPEC-0006-jwt-oidc-verification-and-principal-mapping.md) | JWT/OIDC Verification and Principal Mapping | Active | Active supporting current-state doc | 2026-02-12 |
| [SPEC-0009](./SPEC-0009-caching-and-idempotency.md) | Caching and Idempotency | Active | Active supporting current-state doc | 2026-03-16 |
| [SPEC-0010](./SPEC-0010-observability-analytics-and-activity-rollups.md) | Observability Analytics and Activity Rollups | Active | Active supporting current-state doc | 2026-02-13 |
| [SPEC-0012](./SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md) | SDK Conformance, Versioning, and Compatibility Governance | Active | Active supporting current-state doc | 2026-03-18 |
| [SPEC-0016](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md) | V1 route namespace and literal guardrails | Active | Active supporting current-state doc | 2026-03-19 |
| [SPEC-0017](./SPEC-0017-runtime-component-topology-and-ownership-contract.md) | Runtime component topology and ownership contract | Active | Active supporting current-state doc | 2026-03-22 |
| [SPEC-0018](./SPEC-0018-runtime-configuration-and-startup-validation-contract.md) | Runtime configuration and startup validation contract | Active | Active supporting current-state doc | 2026-03-20 |
| [SPEC-0019](./SPEC-0019-auth-execution-and-threadpool-safety-contract.md) | Auth execution and threadpool safety contract | Active | Active supporting current-state doc | 2026-03-22 |
| [SPEC-0021](./SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md) | Downstream hard-cut integration and consumer validation contract | Active | Active supporting current-state doc | 2026-03-20 |
| [SPEC-0022](./SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md) | Auth0 tenant ops reusable workflow contract | Active | Active supporting current-state doc | 2026-03-04 |
| [SPEC-0025](./SPEC-0025-reusable-workflow-integration-contract.md) | Reusable workflow integration contract | Active | Active supporting current-state doc | 2026-03-05 |
| [SPEC-0026](./SPEC-0026-ci-cd-iam-least-privilege-matrix.md) | CI/CD IAM least-privilege matrix | Active | Active supporting current-state doc | 2026-03-05 |

## Historical / superseded specs

| SPEC | Title | Decision status | Implementation state | Date |
| --- | --- | --- | --- | --- |
| [SPEC-0008](./superseded/SPEC-0008-async-jobs-and-worker-orchestration.md) | Async Jobs and Worker Orchestration | Superseded | Historical traceability only | 2026-03-19 |
| [SPEC-0000](./superseded/SPEC-0000-http-api-contract.md) | Historical public API baseline before the export hard cut | Superseded | Historical traceability only | 2026-03-20 |
| [SPEC-0015](./superseded/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md) | Nova API platform final topology and delivery contract | Superseded | Historical traceability only | 2026-03-03 |
| [SPEC-0020](./superseded/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md) | Architecture authority pack and documentation synchronization contract | Superseded | Historical traceability only | 2026-03-24 |
| [SPEC-0023](./superseded/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md) | Historical SSM runtime base-url contract for deploy validation | Historical | Historical traceability only | 2026-03-05 |
| [SPEC-0024](./SPEC-0024-cloudformation-module-contract.md) | Historical CloudFormation module contract | Historical | Historical traceability only | 2026-03-20 |

Additional superseded specs remain under `./superseded/`.
