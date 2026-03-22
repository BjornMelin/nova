# Architecture Decision Records

- [Architecture Authority Map](../README.md)

- [ADR Template](./ADR-template.md)
- [Canonical Requirements](../requirements.md)
- [Architecture Specifications](../spec/index.md)
- [Operator Runbooks (canonical)](../../runbooks/README.md)

## Active runtime authority pack

Normative runtime authority is layered across:

- route and HTTP contract authority (`ADR-0023`, `SPEC-0000`, `SPEC-0015`,
  `SPEC-0016`, `SPEC-0027`)
- green-field simplification decisions (`ADR-0033` through `ADR-0041`,
  `SPEC-0028`, `SPEC-0029`, and [green-field program](../../plan/greenfield-simplification-program.md))
- runtime package ownership and safety authority (`ADR-0025`, `ADR-0026`,
  `SPEC-0017`, `SPEC-0018`, `SPEC-0019`, `SPEC-0020`)
- downstream/deploy-validation authority (`ADR-0027` through `ADR-0029`,
  `SPEC-0021`, `SPEC-0022`, `SPEC-0023`)

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [ADR-0023](./ADR-0023-hard-cut-v1-canonical-route-surface.md) | Hard cut to a single canonical /v1 API surface | Accepted | 2026-03-03 |
| [ADR-0024](./ADR-0024-layered-architecture-authority-pack.md) | Layered runtime authority pack for the Nova monorepo | Accepted | 2026-03-05 |
| [ADR-0025](./ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md) | Runtime monorepo component boundaries and ownership | Accepted | 2026-03-05 |
| [ADR-0026](./ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md) | Fail-fast runtime configuration and safe auth execution | Accepted | 2026-03-05 |
| [ADR-0027](./ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md) | Hard-cut downstream integration and consumer contract enforcement | Accepted | 2026-03-04 |
| [ADR-0028](./ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md) | Auth0 tenant ops reusable workflow API contract | Accepted | 2026-03-04 |
| [ADR-0029](./ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md) | SSM runtime base URL authority for deploy validation | Accepted | 2026-03-04 |

## Adjacent deploy-governance authority

These ADRs are canonical for deployment-control-plane and CI/CD IAM policy
boundaries, but are not part of the active runtime API authority layer.

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [ADR-0015](./ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md) | Nova API platform final hosting and deployment architecture (2026) | Accepted | 2026-03-03 |
| [ADR-0030](./ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md) | Native-CFN modular stack architecture for Nova infrastructure productization | Accepted | 2026-03-05 |
| [ADR-0031](./ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md) | Reusable GitHub workflow API and versioning policy for deployment automation | Accepted | 2026-03-05 |
| [ADR-0032](./ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md) | OIDC and IAM role partitioning for deploy automation | Accepted | 2026-03-05 |

## SDK and release-artifact governance authority

These identifiers are canonical for SDK topology and release-artifact
governance, separate from the runtime authority pack.

- `ADR-0038` (canonical SDK stacks; supersedes [ADR-0013](./superseded/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md))
- `SPEC-0029` (successor to superseded [SPEC-0011](../spec/superseded/SPEC-0011-multi-language-sdk-architecture-and-package-map.md))
- `SPEC-0012`

## Green-field simplification authority (2026)

Target-state decisions for single-runtime auth, bearer-only public contract,
direct worker persistence, native OpenAPI, shared ASGI middleware, async-first
public surface, per-language SDK stacks, AWS composite platform, and repo
rebaseline. See [greenfield-authority-map.md](../../plan/greenfield-authority-map.md).

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [ADR-0033](./ADR-0033-single-runtime-auth-authority.md) | Green-field single runtime auth authority | Accepted | 2026-03-19 |
| [ADR-0034](./ADR-0034-bearer-jwt-public-auth-contract.md) | Green-field bearer JWT public auth contract | Accepted | 2026-03-19 |
| [ADR-0035](./ADR-0035-worker-direct-result-persistence.md) | Green-field worker direct result persistence | Accepted | 2026-03-19 |
| [ADR-0036](./ADR-0036-native-fastapi-openapi-contract.md) | Green-field native FastAPI OpenAPI contract expression | Accepted | 2026-03-19 |
| [ADR-0037](./ADR-0037-async-first-public-surface.md) | Green-field async-first public surface | Accepted | 2026-03-22 |
| [ADR-0038](./ADR-0038-sdk-architecture-by-language.md) | Green-field SDK architecture by language | Accepted | 2026-03-19 |
| [ADR-0039](./ADR-0039-aws-target-platform.md) | Green-field AWS target platform | Accepted | 2026-03-19 |
| [ADR-0040](./ADR-0040-repo-rebaseline-after-cuts.md) | Green-field repo rebaseline after architecture cuts | Accepted | 2026-03-19 |
| [ADR-0041](./ADR-0041-shared-pure-asgi-middleware-and-errors.md) | Green-field shared pure ASGI middleware and errors | Accepted | 2026-03-19 |

## Active supporting decisions

These ADRs remain accepted and implemented, but they are not the primary
operator-authority entrypoint identifiers.

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [ADR-0000](./ADR-0000-fastapi-microservice.md) | Implement the File Transfer API as a FastAPI service | Accepted | 2026-02-11 |
| [ADR-0001](./ADR-0001-deployment-on-ecs-fargate-behind-alb.md) | Deploy on ECS Fargate behind ALB with same-origin routing | Accepted (partially superseded) | 2026-03-05 |
| [ADR-0002](./ADR-0002-openapi-as-contract-and-sdk-generation.md) | Treat OpenAPI as the contract and generate client SDKs from it | Accepted | 2026-02-11 |
| [ADR-0003](./ADR-0003-api-docs-site-mkdocs-material-plus-scalar.md) | API documentation site uses MkDocs Material and Scalar API Reference | Accepted | 2026-02-11 |
| [ADR-0004](./ADR-0004-canonical-oidc-jwt-verifier-adoption.md) | Adopt oidc-jwt-verifier as the canonical JWT/OIDC verification engine | Accepted | 2026-02-12 |
| [ADR-0006](./ADR-0006-async-orchestration-sqs-ecs-worker.md) | Use SQS + ECS worker for initial async orchestration | Accepted | 2026-02-12 |
| [ADR-0007](./ADR-0007-two-tier-cache-and-idempotency-store.md) | Adopt two-tier cache with idempotency replay storage | Accepted | 2026-02-13 |
| [ADR-0008](./ADR-0008-runtime-support-levels-sidecar-embedded-standalone.md) | Runtime support levels: sidecar GA, embedded bridge, standalone beta | Accepted | 2026-02-12 |
| [ADR-0009](./ADR-0009-observability-analytics-emf-dynamodb-cloudwatch.md) | Observability stack: EMF metrics, DynamoDB rollups, CloudWatch dashboards | Accepted | 2026-02-12 |
| [ADR-0010](./ADR-0010-enqueue-failure-and-readiness-semantics.md) | Fail enqueue on queue publish errors and scope readiness to critical dependencies | Accepted | 2026-03-05 |
| [ADR-0011](./ADR-0011-cicd-hybrid-github-aws-promotion.md) | Hybrid CI/CD with GitHub CI and AWS-native Dev to Prod promotion | Accepted (umbrella decision) | 2026-03-05 |
| [ADR-0012](./ADR-0012-no-lambda-runtime-scope.md) | Preserve ECS and SQS runtime scope and exclude Lambda orchestration | Accepted | 2026-02-24 |
| [ADR-0022](./ADR-0022-release-validation-read-access-iam-iac.md) | Release validation read role codified in Nova IaC for reproducible validation access | Accepted | 2026-03-02 |

## Superseded

These ADRs are retained for traceability only and are not active authority.

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [ADR-0014](./superseded/ADR-0014-container-craft-capability-absorption-and-repo-retirement.md) | Absorb remaining container-craft Nova capabilities into nova and retire container-craft (historical) | Superseded | 2026-02-28 |
| [ADR-0016](./superseded/ADR-0016-minimal-governance-final-state-operator-path.md) | Minimal governance final-state operator path | Superseded | 2026-03-02 |
| [ADR-0005](./superseded/ADR-0005-add-dedicated-nova-auth-api-service.md) | Add dedicated nova-auth-api service while keeping local verification default | Superseded | 2026-03-19 |
| [ADR-0013](./superseded/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md) | Final-state SDK topology (pre–openapi-typescript / pre-auth-SDK removal) | Superseded | 2026-03-18 |
| [ADR-0025](./superseded/ADR-0025-reusable-workflow-api-and-versioning-policy.md) | Reusable GitHub workflow API and versioning policy (pre-filename split) | Superseded | 2026-03-09 |
| [ADR-0026](./superseded/ADR-0026-oidc-iam-role-partitioning-for-deploy-automation.md) | OIDC and IAM role partitioning (duplicate identifier before ADR-0032) | Superseded | 2026-03-03 |
