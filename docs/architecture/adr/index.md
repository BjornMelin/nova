# Architecture Decision Records

Status: Active index
Last reviewed: 2026-04-07

## Active canonical ADRs

| ADR | Title | Decision status | Implementation state | Date |
| --- | --- | --- | --- | --- |
| [ADR-0033](./ADR-0033-canonical-serverless-platform.md) | Canonical serverless platform | Accepted | Active baseline | 2026-03-25 |
| [ADR-0034](./ADR-0034-eliminate-auth-service-and-session-auth.md) | Eliminate auth service and session auth | Accepted | Active baseline | 2026-03-25 |
| [ADR-0035](./ADR-0035-replace-generic-jobs-with-export-workflows.md) | Replace generic jobs with export workflows | Accepted | Active baseline | 2026-03-25 |
| [ADR-0036](./ADR-0036-dynamodb-idempotency-no-redis.md) | DynamoDB idempotency and transient state, no Redis | Accepted | Active baseline | 2026-03-25 |
| [ADR-0037](./ADR-0037-sdk-generation-consolidation.md) | Consolidate SDK generation and package layout | Accepted | Active baseline | 2026-03-25 |
| [ADR-0038](./ADR-0038-docs-authority-reset.md) | Reset docs authority | Accepted | Active baseline | 2026-03-25 |
| [ADR-0039](./ADR-0039-lambda-runtime-bootstrap-and-runtime-container.md) | Explicit Lambda runtime bootstrap and typed runtime container | Accepted | Active baseline | 2026-04-06 |

## Active supporting ADRs

| ADR | Title | Decision status | Implementation state | Date |
| --- | --- | --- | --- | --- |
| [ADR-0000](./ADR-0000-fastapi-microservice.md) | Implement the File Transfer API as a FastAPI service | Accepted | Active supporting current-state doc | 2026-02-11 |
| [ADR-0002](./ADR-0002-openapi-as-contract-and-sdk-generation.md) | Treat OpenAPI as the contract and generate client SDKs from it | Accepted | Active supporting current-state doc | 2026-02-11 |
| [ADR-0003](./ADR-0003-api-docs-site-mkdocs-material-plus-scalar.md) | API documentation site uses MkDocs Material and Scalar API Reference | Accepted | Active supporting current-state doc | 2026-02-11 |
| [ADR-0004](./ADR-0004-canonical-oidc-jwt-verifier-adoption.md) | Adopt oidc-jwt-verifier as the canonical JWT/OIDC verification engine | Accepted | Active supporting current-state doc | 2026-02-12 |
| [ADR-0008](./ADR-0008-runtime-support-levels-sidecar-embedded-standalone.md) | Runtime support levels: sidecar GA, embedded bridge, standalone beta | Accepted | Active supporting current-state doc | 2026-02-12 |
| [ADR-0009](./ADR-0009-observability-analytics-emf-dynamodb-cloudwatch.md) | Observability stack: EMF metrics, DynamoDB rollups, CloudWatch dashboards | Accepted | Active supporting current-state doc | 2026-02-12 |
| [ADR-0010](./ADR-0010-enqueue-failure-and-readiness-semantics.md) | Fail enqueue on queue publish errors and scope readiness to critical dependencies | Accepted | Active supporting current-state doc | 2026-03-09 |
| [ADR-0011](./ADR-0011-cicd-hybrid-github-aws-promotion.md) | Hybrid CI/CD with GitHub CI and AWS-native Dev to Prod promotion | Accepted | Active supporting current-state doc | 2026-03-05 |
| [ADR-0023](./ADR-0023-hard-cut-v1-canonical-route-surface.md) | Hard cut to a single canonical /v1 API surface | Accepted | Active supporting current-state doc | 2026-03-03 |
| [ADR-0024](./ADR-0024-layered-architecture-authority-pack.md) | Layered runtime authority pack for the Nova monorepo | Accepted | Active supporting current-state doc | 2026-03-05 |
| [ADR-0025](./ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md) | Runtime monorepo component boundaries and ownership | Accepted | Active supporting current-state doc | 2026-03-22 |
| [ADR-0026](./ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md) | Fail-fast runtime configuration and safe auth execution | Accepted | Active supporting current-state doc | 2026-03-20 |
| [ADR-0027](./ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md) | Hard-cut downstream integration and consumer contract enforcement | Accepted | Active supporting current-state doc | 2026-03-04 |
| [ADR-0028](./ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md) | Auth0 tenant ops reusable workflow API contract | Accepted | Active supporting current-state doc | 2026-03-04 |
| [ADR-0031](./ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md) | Reusable GitHub workflow API and versioning policy for deployment automation | Accepted | Active supporting current-state doc | 2026-03-09 |
| [ADR-0032](./ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md) | OIDC and IAM role partitioning for deploy automation | Accepted | Active supporting current-state doc | 2026-03-03 |
| [ADR-0042](./ADR-0042-large-file-transfer-observability-and-benchmark-baseline.md) | Large-file transfer observability and benchmark baseline | Accepted | Active supporting current-state doc | 2026-04-03 |

## Historical / superseded ADRs

| ADR | Title | Decision status | Implementation state | Date |
| --- | --- | --- | --- | --- |
| [ADR-0001](./superseded/ADR-0001-deployment-on-ecs-fargate-behind-alb.md) | Deploy on ECS Fargate behind ALB | Superseded | Historical traceability only | 2026-03-05 |
| [ADR-0022](./ADR-0022-release-validation-read-access-iam-iac.md) | Codify release validation read access in Nova IaC | Historical | Historical traceability only | 2026-03-02 |
| [ADR-0029](./ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md) | SSM runtime base URL authority for deploy validation | Historical | Historical traceability only | 2026-03-05 |
| [ADR-0007](./superseded/ADR-0007-two-tier-cache-and-idempotency-store.md) | Adopt two-tier cache with idempotency replay storage | Superseded | Historical traceability only | 2026-02-13 |
| [ADR-0006](./superseded/ADR-0006-async-orchestration-sqs-ecs-worker.md) | Use SQS + ECS worker for initial async orchestration | Superseded | Historical traceability only | 2026-02-12 |
| [ADR-0012](./superseded/ADR-0012-no-lambda-runtime-scope.md) | Preserve ECS and SQS runtime scope and exclude Lambda orchestration | Superseded | Historical traceability only | 2026-02-24 |
| [ADR-0015](./superseded/ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md) | Nova API platform final hosting and deployment architecture (2026) | Superseded | Historical traceability only | 2026-03-03 |
| [ADR-0030](./superseded/ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md) | Native-CFN modular stack architecture for Nova infrastructure productization | Superseded | Historical traceability only | 2026-03-05 |

Additional superseded ADRs remain under `./superseded/`.
