# Architecture Decision Records

Status: Active index
Last reviewed: 2026-03-28

## Active canonical ADRs

| ADR | Title | Decision status | Implementation state | Date |
| --- | --- | --- | --- | --- |
| [ADR-0000](./ADR-0000-fastapi-microservice.md) | Implement the File Transfer API as a FastAPI service | Accepted | Active baseline | 2026-02-11 |
| [ADR-0002](./ADR-0002-openapi-as-contract-and-sdk-generation.md) | Treat OpenAPI as the contract and generate client SDKs from it | Accepted | Active baseline | 2026-02-11 |
| [ADR-0004](./ADR-0004-canonical-oidc-jwt-verifier-adoption.md) | Adopt oidc-jwt-verifier as the canonical JWT/OIDC verification engine | Accepted | Active baseline | 2026-02-12 |
| [ADR-0023](./ADR-0023-hard-cut-v1-canonical-route-surface.md) | Hard cut to a single canonical /v1 API surface | Accepted | Active baseline | 2026-03-03 |
| [ADR-0024](./ADR-0024-layered-architecture-authority-pack.md) | Layered runtime authority pack for the Nova monorepo | Accepted | Active baseline | 2026-03-05 |
| [ADR-0025](./ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md) | Runtime monorepo component boundaries and ownership | Accepted | Active baseline | 2026-03-05 |
| [ADR-0026](./ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md) | Fail-fast runtime configuration and safe auth execution | Accepted | Active baseline | 2026-03-05 |
| [ADR-0027](./ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md) | Hard-cut downstream integration and consumer contract enforcement | Accepted | Active baseline | 2026-03-04 |
| [ADR-0028](./ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md) | Auth0 tenant ops reusable workflow API contract | Accepted | Active baseline | 2026-03-04 |
| [ADR-0033](./ADR-0033-canonical-serverless-platform.md) | Canonical serverless platform | Accepted | Active baseline | 2026-03-25 |
| [ADR-0034](./ADR-0034-eliminate-auth-service-and-session-auth.md) | Eliminate auth service and session auth | Accepted | Active baseline | 2026-03-25 |
| [ADR-0035](./ADR-0035-replace-generic-jobs-with-export-workflows.md) | Replace generic jobs with export workflows | Accepted | Active baseline | 2026-03-25 |
| [ADR-0036](./ADR-0036-dynamodb-idempotency-no-redis.md) | DynamoDB idempotency and transient state, no Redis | Accepted | Active baseline | 2026-03-25 |
| [ADR-0037](./ADR-0037-sdk-generation-consolidation.md) | Consolidate SDK generation and package layout | Accepted | Active baseline | 2026-03-25 |
| [ADR-0038](./ADR-0038-docs-authority-reset.md) | Reset docs authority | Accepted | Active baseline | 2026-03-25 |

## Historical / superseded

Older ECS-era, deploy-governance, and pre-wave-2 ADRs remain under this
directory or `./superseded/` for traceability, but they are not part of the
active canonical authority surface.
