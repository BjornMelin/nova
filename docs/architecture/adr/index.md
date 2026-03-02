# Architecture Decision Records

- [ADR Template](./ADR-template.md)
- [Canonical Requirements](../requirements.md)
- [Architecture Specifications](../spec/index.md)
- [Operator Runbooks (canonical)](../../runbooks/README.md)

## ADR Catalog

Note: `ADR-0015` is accepted as target-state architecture and its delivery is
tracked as implementation pending via `SPEC-0015`.

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [ADR-0000](./ADR-0000-fastapi-microservice.md) | Implement the File Transfer API as a FastAPI service | Accepted | 2026-02-11 |
| [ADR-0001](./ADR-0001-deployment-on-ecs-fargate-behind-alb.md) | Deploy on ECS Fargate behind ALB with same-origin routing | Accepted | 2026-02-11 |
| [ADR-0002](./ADR-0002-openapi-as-contract-and-sdk-generation.md) | Treat OpenAPI as the contract and generate client SDKs from it | Accepted | 2026-02-11 |
| [ADR-0003](./ADR-0003-api-docs-site-mkdocs-material-plus-scalar.md) | API documentation site uses MkDocs Material and Scalar API Reference | Accepted | 2026-02-11 |
| [ADR-0004](./ADR-0004-canonical-oidc-jwt-verifier-adoption.md) | Adopt oidc-jwt-verifier as the canonical JWT/OIDC verification engine | Accepted | 2026-02-12 |
| [ADR-0005](./ADR-0005-add-dedicated-nova-auth-api-service.md) | Add dedicated nova-auth-api service while keeping local verification default | Accepted | 2026-02-12 |
| [ADR-0006](./ADR-0006-async-orchestration-sqs-ecs-worker.md) | Use SQS + ECS worker for initial async orchestration | Accepted | 2026-02-12 |
| [ADR-0007](./ADR-0007-two-tier-cache-and-idempotency-store.md) | Adopt two-tier cache with idempotency replay storage | Accepted | 2026-02-13 |
| [ADR-0008](./ADR-0008-runtime-support-levels-sidecar-embedded-standalone.md) | Runtime support levels: sidecar GA, embedded bridge, standalone beta | Accepted | 2026-02-12 |
| [ADR-0009](./ADR-0009-observability-analytics-emf-dynamodb-cloudwatch.md) | Observability stack: EMF metrics, DynamoDB rollups, CloudWatch dashboards | Accepted | 2026-02-12 |
| [ADR-0010](./ADR-0010-enqueue-failure-and-readiness-semantics.md) | Fail enqueue on queue publish errors and scope readiness to critical dependencies | Accepted | 2026-02-23 |
| [ADR-0011](./ADR-0011-cicd-hybrid-github-aws-promotion.md) | Hybrid CI/CD with GitHub CI and AWS-native Dev to Prod promotion | Accepted | 2026-02-24 |
| [ADR-0012](./ADR-0012-no-lambda-runtime-scope.md) | Preserve ECS and SQS runtime scope and exclude Lambda orchestration | Accepted | 2026-02-24 |
| [ADR-0013](./ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md) | Final-state SDK topology uses generated contract-core clients plus thin language adapters | Accepted | 2026-02-28 |
| [ADR-0014](./ADR-0014-container-craft-capability-absorption-and-repo-retirement.md) | Absorb remaining container-craft Nova capabilities into nova and retire container-craft | Accepted | 2026-02-28 |
| [ADR-0015](./ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md) | Nova API platform final hosting and deployment architecture (2026) | Accepted | 2026-03-01 |
| [ADR-0016](./ADR-0016-minimal-governance-final-state-operator-path.md) | Minimal governance final-state operator path | Accepted | 2026-03-02 |
