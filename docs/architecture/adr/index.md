# Architecture Decision Records

Status: Active index
Last reviewed: 2026-03-25

## Status model

- **Implemented** — reflected in the current repository and current runbooks
- **Accepted, planned** — approved target-state decision for the wave-2 hard cut;
  not fully implemented yet
- **Superseded** — traceability only

This file is the ADR catalog and status index.

## Current implemented baseline

| ADR | Title | Decision status | Implementation state | Date |
| --- | --- | --- | --- | --- |
| [ADR-0000](./ADR-0000-fastapi-microservice.md) | Implement the File Transfer API as a FastAPI service | Accepted | Implemented | 2026-02-11 |
| [ADR-0001](./ADR-0001-deployment-on-ecs-fargate-behind-alb.md) | Deploy on ECS Fargate behind ALB | Accepted | Implemented baseline | 2026-02-11 |
| [ADR-0002](./ADR-0002-openapi-as-contract-and-sdk-generation.md) | Treat OpenAPI as the contract and generate client SDKs from it | Accepted | Implemented baseline | 2026-02-11 |
| [ADR-0003](./ADR-0003-api-docs-site-mkdocs-material-plus-scalar.md) | API documentation site uses MkDocs Material and Scalar API Reference | Accepted | Implemented baseline | 2026-02-11 |
| [ADR-0004](./ADR-0004-canonical-oidc-jwt-verifier-adoption.md) | Adopt oidc-jwt-verifier as the canonical JWT/OIDC verification engine | Accepted | Implemented baseline | 2026-02-12 |
| [ADR-0006](./ADR-0006-async-orchestration-sqs-ecs-worker.md) | Use SQS + ECS worker for initial async orchestration | Accepted | Implemented baseline | 2026-02-12 |
| [ADR-0007](./ADR-0007-two-tier-cache-and-idempotency-store.md) | Adopt two-tier cache with idempotency replay storage | Accepted | Implemented baseline | 2026-02-13 |
| [ADR-0008](./ADR-0008-runtime-support-levels-sidecar-embedded-standalone.md) | Runtime support levels: sidecar GA, embedded bridge, standalone beta | Accepted | Implemented baseline | 2026-02-12 |
| [ADR-0009](./ADR-0009-observability-analytics-emf-dynamodb-cloudwatch.md) | Observability stack: EMF metrics, DynamoDB rollups, CloudWatch dashboards | Accepted | Implemented baseline | 2026-02-12 |
| [ADR-0010](./ADR-0010-enqueue-failure-and-readiness-semantics.md) | Fail enqueue on queue publish errors and scope readiness to critical dependencies | Accepted | Implemented baseline | 2026-02-13 |
| [ADR-0011](./ADR-0011-cicd-hybrid-github-aws-promotion.md) | Hybrid CI/CD with GitHub CI and AWS-native Dev to Prod promotion | Accepted | Implemented baseline | 2026-02-18 |
| [ADR-0012](./ADR-0012-no-lambda-runtime-scope.md) | Preserve ECS and SQS runtime scope and exclude Lambda orchestration | Accepted | Implemented baseline | 2026-02-24 |
| [ADR-0015](./ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md) | Nova API platform final hosting and deployment architecture (2026) | Accepted | Implemented baseline | 2026-03-03 |
| [ADR-0022](./ADR-0022-release-validation-read-access-iam-iac.md) | Release validation read role codified in Nova IaC for reproducible validation access | Accepted | Implemented baseline | 2026-03-02 |
| [ADR-0023](./ADR-0023-hard-cut-v1-canonical-route-surface.md) | Hard cut to a single canonical /v1 API surface | Accepted | Implemented baseline | 2026-03-03 |
| [ADR-0024](./ADR-0024-layered-architecture-authority-pack.md) | Layered runtime authority pack for the Nova monorepo | Accepted | Implemented baseline | 2026-03-05 |
| [ADR-0025](./ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md) | Runtime monorepo component boundaries and ownership | Accepted | Implemented baseline | 2026-03-05 |
| [ADR-0026](./ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md) | Fail-fast runtime configuration and safe auth execution | Accepted | Implemented baseline | 2026-03-05 |
| [ADR-0027](./ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md) | Hard-cut downstream integration and consumer contract enforcement | Accepted | Implemented baseline | 2026-03-04 |
| [ADR-0028](./ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md) | Auth0 tenant ops reusable workflow API contract | Accepted | Implemented baseline | 2026-03-04 |
| [ADR-0029](./ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md) | SSM runtime base URL authority for deploy validation | Accepted | Implemented baseline | 2026-03-04 |
| [ADR-0030](./ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md) | Native-CFN modular stack architecture for Nova infrastructure productization | Accepted | Implemented baseline | 2026-03-05 |
| [ADR-0031](./ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md) | Reusable GitHub workflow API and versioning policy for deployment automation | Accepted | Implemented baseline | 2026-03-05 |
| [ADR-0032](./ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md) | OIDC and IAM role partitioning for deploy automation | Accepted | Implemented baseline | 2026-03-05 |

## Approved target-state program

| ADR | Title | Decision status | Implementation state | Date |
| --- | --- | --- | --- | --- |
| [ADR-0033](./ADR-0033-canonical-serverless-platform.md) | Canonical serverless platform | Accepted | Planned target | 2026-03-25 |
| [ADR-0034](./ADR-0034-eliminate-auth-service-and-session-auth.md) | Eliminate auth service and session auth | Accepted | Planned target | 2026-03-25 |
| [ADR-0035](./ADR-0035-replace-generic-jobs-with-export-workflows.md) | Replace generic jobs with export workflows | Accepted | Planned target | 2026-03-25 |
| [ADR-0036](./ADR-0036-dynamodb-idempotency-no-redis.md) | DynamoDB idempotency and transient state, no Redis | Accepted | Planned target | 2026-03-25 |
| [ADR-0037](./ADR-0037-sdk-generation-consolidation.md) | Consolidate SDK generation and package layout | Accepted | Planned target | 2026-03-25 |
| [ADR-0038](./ADR-0038-docs-authority-reset.md) | Reset docs authority | Accepted | Applied to docs pack / code still planned | 2026-03-25 |

## Superseded

Use `./superseded/README.md` and the files in `./superseded/` for traceability
only. This now includes both older legacy supersessions and the unimplemented
wave-1 green-field drafts that were replaced by the wave-2 target set before
code landed.
