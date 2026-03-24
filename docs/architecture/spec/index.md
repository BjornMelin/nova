# Architecture Specifications

- [Architecture Authority Map](../README.md)

- [Canonical Requirements](../requirements.md)
- [ADR Index](../adr/index.md)
- [Reference Links](./REFERENCES.md)
- [Operator Runbooks (canonical)](../../runbooks/README.md)

## Catalog Use

Use [`../README.md`](../README.md) for the narrative authority map and the
canonical route chain (`requirements -> ADR-0023 -> SPEC-0000 -> SPEC-0016 ->
SPEC-0027`). This file is the SPEC catalog and status index.

| SPEC | Title | Status | Date |
| --- | --- | --- | --- |
| [SPEC-0000](./SPEC-0000-http-api-contract.md) | HTTP API Contract | Active | 2026-03-03 |
| [SPEC-0001](./SPEC-0001-security-model.md) | Security Model | Active | 2026-03-03 |
| [SPEC-0002](./SPEC-0002-s3-integration.md) | S3 Integration | Active | 2026-02-11 |
| [SPEC-0003](./SPEC-0003-observability.md) | Observability | Active | 2026-03-03 |
| [SPEC-0004](./SPEC-0004-ci-cd-and-docs.md) | CI/CD and Documentation Automation | Active | 2026-03-03 |
| [SPEC-0005](./SPEC-0005-abuse-prevention-and-quotas.md) | Abuse Prevention and Quotas | Active | 2026-03-03 |
| [SPEC-0006](./SPEC-0006-jwt-oidc-verification-and-principal-mapping.md) | JWT/OIDC Verification and Principal Mapping | Active | 2026-02-12 |
| [SPEC-0008](./SPEC-0008-async-jobs-and-worker-orchestration.md) | Async Jobs and Worker Orchestration | Active | 2026-03-19 |
| [SPEC-0009](./SPEC-0009-caching-and-idempotency.md) | Caching and Idempotency | Active | 2026-02-13 |
| [SPEC-0010](./SPEC-0010-observability-analytics-and-activity-rollups.md) | Observability Analytics and Activity Rollups | Active | 2026-02-13 |
| [SPEC-0012](./SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md) | SDK conformance, versioning, and compatibility governance for Python public, release-grade TypeScript, and first-class internal R packages | Active | 2026-03-18 |
| [SPEC-0015](./SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md) | Nova API platform final topology and delivery contract | Active | 2026-03-03 |
| [SPEC-0016](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md) | Hard-cut v1 route contract and route-literal guardrails | Active | 2026-03-03 |
| [SPEC-0017](./SPEC-0017-runtime-component-topology-and-ownership-contract.md) | Runtime component topology and ownership contract | Active | 2026-03-07 |
| [SPEC-0018](./SPEC-0018-runtime-configuration-and-startup-validation-contract.md) | Runtime configuration and startup validation contract | Active | 2026-03-06 |
| [SPEC-0019](./SPEC-0019-auth-execution-and-threadpool-safety-contract.md) | Auth execution and threadpool safety contract | Active | 2026-03-22 |
| [SPEC-0020](./SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md) | Architecture authority pack and documentation synchronization contract | Active | 2026-03-05 |
| [SPEC-0021](./SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md) | Downstream hard-cut integration and consumer validation contract | Active | 2026-03-04 |
| [SPEC-0022](./SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md) | Auth0 tenant ops reusable workflow contract | Active | 2026-03-04 |
| [SPEC-0023](./SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md) | SSM runtime base-url contract for deploy validation | Active | 2026-03-04 |
| [SPEC-0024](./SPEC-0024-cloudformation-module-contract.md) | CloudFormation module contract | Active | 2026-03-05 |
| [SPEC-0025](./SPEC-0025-reusable-workflow-integration-contract.md) | Reusable workflow integration contract | Active | 2026-03-05 |
| [SPEC-0026](./SPEC-0026-ci-cd-iam-least-privilege-matrix.md) | CI/CD IAM least-privilege matrix | Active | 2026-03-05 |
| [SPEC-0027](./SPEC-0027-public-http-contract-revision-and-bearer-auth.md) | Public HTTP contract revision and bearer auth | Active | 2026-03-19 |
| [SPEC-0028](./SPEC-0028-worker-job-lifecycle-and-direct-result-path.md) | Worker job lifecycle and direct result path | Active | 2026-03-19 |
| [SPEC-0029](./SPEC-0029-sdk-architecture-and-artifact-contract.md) | SDK architecture and artifact contract | Active | 2026-03-19 |

## Superseded specs

These specs are retained for traceability only and are not active authority.

| SPEC | Title | Status | Date |
| --- | --- | --- | --- |
| [SPEC-0007](./superseded/SPEC-0007-auth-api-contract.md) | Auth API Contract | Superseded | 2026-03-19 |
| [SPEC-0011](./superseded/SPEC-0011-multi-language-sdk-architecture-and-package-map.md) | Public Python SDK architecture with release-grade TypeScript and first-class internal R package map | Superseded | 2026-03-18 |
| [SPEC-0017 (CloudFormation)](./superseded/SPEC-0017-cloudformation-module-contract.md) | CloudFormation module contract (retired filename; successor SPEC-0024) | Superseded | 2026-03-05 |
| [SPEC-0018 (workflows)](./superseded/SPEC-0018-reusable-workflow-integration-contract.md) | Reusable workflow integration contract (retired filename; successor SPEC-0025) | Superseded | 2026-03-04 |
| [SPEC-0019 (IAM)](./superseded/SPEC-0019-ci-cd-iam-least-privilege-and-role-boundary-contract.md) | CI/CD IAM least-privilege and role-boundary contract (retired filename; successor SPEC-0026) | Superseded | 2026-03-03 |
| [SPEC-0013](./superseded/SPEC-0013-container-craft-capability-absorption-execution-spec.md) | Container-craft capability absorption execution spec | Superseded | 2026-02-28 |
| [SPEC-0014](./superseded/SPEC-0014-container-craft-capability-inventory-and-absorption-map.md) | Container-craft capability inventory and Nova absorption target map | Superseded | 2026-02-28 |
