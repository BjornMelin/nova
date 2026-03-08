# Architecture Specifications

- [Canonical Requirements](../requirements.md)
- [ADR Index](../adr/index.md)
- [Reference Links](./REFERENCES.md)
- [Operator Runbooks (canonical)](../../runbooks/README.md)

## Active runtime authority pack

These specs define the live runtime and documentation authority graph used by
the repository-wide active authority set.

| SPEC | Title | Status | Date |
| --- | --- | --- | --- |
| [SPEC-0000](./SPEC-0000-http-api-contract.md) | HTTP API contract | Active | 2026-03-03 |
| [SPEC-0015](./SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md) | Nova API platform final topology and delivery contract | Active | 2026-03-03 |
| [SPEC-0016](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md) | Hard-cut v1 route contract and route-literal guardrails | Active | 2026-03-03 |
| [SPEC-0017](./SPEC-0017-runtime-component-topology-and-ownership-contract.md) | Runtime component topology and ownership contract | Active | 2026-03-05 |
| [SPEC-0018](./SPEC-0018-runtime-configuration-and-startup-validation-contract.md) | Runtime configuration and startup validation contract | Active | 2026-03-05 |
| [SPEC-0019](./SPEC-0019-auth-execution-and-threadpool-safety-contract.md) | Auth execution and threadpool safety contract | Active | 2026-03-05 |
| [SPEC-0020](./SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md) | Architecture authority pack and documentation synchronization contract | Active | 2026-03-05 |
| [SPEC-0021](./SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md) | Downstream hard-cut integration and consumer validation contract | Active | 2026-03-04 |
| [SPEC-0022](./SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md) | Auth0 tenant ops reusable workflow contract | Active | 2026-03-04 |
| [SPEC-0023](./SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md) | SSM runtime base-url contract for deploy validation | Active | 2026-03-05 |

## Active supporting specs

These specs remain active and implemented, but they support the authority pack
rather than acting as the primary top-level runtime authority identifiers.

| SPEC | Title | Status | Date |
| --- | --- | --- | --- |
| [SPEC-0001](./SPEC-0001-security-model.md) | Security model | Active | 2026-03-03 |
| [SPEC-0002](./SPEC-0002-s3-integration.md) | S3 integration | Active | 2026-02-11 |
| [SPEC-0003](./SPEC-0003-observability.md) | Observability | Active | 2026-03-03 |
| [SPEC-0004](./SPEC-0004-ci-cd-and-docs.md) | CI/CD and documentation automation | Active | 2026-03-05 |
| [SPEC-0005](./SPEC-0005-abuse-prevention-and-quotas.md) | Abuse prevention and quotas | Active | 2026-03-03 |
| [SPEC-0006](./SPEC-0006-jwt-oidc-verification-and-principal-mapping.md) | JWT/OIDC verification and principal mapping | Active | 2026-02-12 |
| [SPEC-0007](./SPEC-0007-auth-api-contract.md) | Auth API contract | Active | 2026-03-03 |
| [SPEC-0008](./SPEC-0008-async-jobs-and-worker-orchestration.md) | Async jobs and worker orchestration | Active | 2026-03-03 |
| [SPEC-0009](./SPEC-0009-caching-and-idempotency.md) | Caching and idempotency | Active | 2026-02-13 |
| [SPEC-0010](./SPEC-0010-observability-analytics-and-activity-rollups.md) | Observability analytics and activity rollups | Active | 2026-02-13 |
| [SPEC-0011](./SPEC-0011-multi-language-sdk-architecture-and-package-map.md) | Multi-language SDK architecture and package map | Active | 2026-03-07 |
| [SPEC-0012](./SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md) | SDK governance for Python release-grade and deferred TS/R catalogs | Active | 2026-03-05 |
| [SPEC-0024](./SPEC-0024-cloudformation-module-contract.md) | CloudFormation module contract | Active | 2026-03-05 |
| [SPEC-0025](./SPEC-0025-reusable-workflow-integration-contract.md) | Reusable workflow integration contract | Active | 2026-03-05 |
| [SPEC-0026](./SPEC-0026-ci-cd-iam-least-privilege-matrix.md) | CI/CD IAM least-privilege matrix | Active | 2026-03-05 |

## Superseded

These specs are preserved for traceability only and must not appear in active
authority lists.

| SPEC | Title | Status | Date |
| --- | --- | --- | --- |
| [SPEC-0020](./superseded/SPEC-0020-rollout-and-validation-strategy.md) | Rollout and validation strategy | Superseded | 2026-03-05 |

## Historical-only references

- `docs/history/2026-02-cutover/architecture/spec/SPEC-0013-container-craft-capability-absorption-execution-spec.md`
- `docs/history/2026-02-cutover/architecture/spec/SPEC-0014-container-craft-capability-inventory-and-absorption-map.md`
