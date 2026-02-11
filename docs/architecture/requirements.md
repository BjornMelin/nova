# Requirements (aws-file-transfer-api)

**Status:** Canonical and definitive requirements source  
**Last updated:** 2026-02-11

This file is the single source of truth for requirements. It merges and supersedes
previous split requirement documents.

## Scope

Defines requirements for provisioning and operating a File Transfer API control plane
that orchestrates direct-to-S3 uploads/downloads via presigned URLs and multipart
uploads, deployed on ECS/Fargate behind ALB via container-craft.

Primary consumers:

- Plotly Dash apps (Python)
- R Shiny apps (HTTP client)
- Next.js / TypeScript apps (HTTP client + generated SDK)

## Requirement crosswalk

Core IDs (`FR-000x`, `NFR-000x`) are primary architecture-facing IDs used by ADRs and
SPECs. Domain IDs (`FR-FT-xxx`, `NFR-FT-xxx`) capture AWS/file-transfer specific detail.

| Core ID | Detailed ID(s) |
| --- | --- |
| FR-0000 | FR-FT-001, FR-FT-002, FR-FT-003 |
| FR-0001 | FR-FT-002 |
| FR-0002 | FR-FT-004 |
| FR-0003 | FR-FT-005 |
| FR-0004 | FR-FT-006 |
| NFR-0000 | NFR-FT-005 |
| NFR-0001 | NFR-FT-007 |

## Functional requirements (core)

### FR-0000: Control-plane endpoints

The service MUST implement:

- `POST /api/file-transfer/uploads/initiate`
- `POST /api/file-transfer/uploads/sign-parts`
- `POST /api/file-transfer/uploads/complete`
- `POST /api/file-transfer/uploads/abort`
- `POST /api/file-transfer/downloads/presign`

The API is control-plane only and MUST NOT proxy upload/download file bytes.

### FR-0001: S3 multipart correctness

The service MUST:

- enforce multipart constraints (max 10,000 parts)
- support configurable part size and multipart threshold
- require `ETag` values for multipart completion
- support multipart abort flows
- support very large objects via multipart (policy-configurable upper bounds)

### FR-0002: Key generation and scoping

The service MUST:

- generate object keys server-side
- enforce scope-based key ownership checks on all follow-up operations
- restrict keys to approved configured prefixes

### FR-0003: Transfer Acceleration support

When enabled by environment and infrastructure, presigned URLs MUST use S3 Transfer
Acceleration-compatible configuration.

### FR-0004: Auth and authorization (pluggable)

The service MUST support pluggable auth modes and authorization enforcement:

- JWT/OIDC bearer-token mode (recommended)
- same-origin/session-derived scope mode for app-integrated deployments

The service MUST derive `scope_id` from trusted auth context and enforce scope rules.

## Non-functional requirements (core)

### NFR-0000: Observability

The service MUST provide:

- health endpoint support (`/healthz`, and compatibility `/` if platform requires)
- structured logs with request correlation IDs
- no logging of presigned URL query strings
- metrics hooks for request count, latency, and error rates

### NFR-0001: Documentation automation

The service MUST publish OpenAPI-driven API documentation automatically on changes and
maintain docs automation as part of CI/CD.

## Detailed AWS/file-transfer requirements

### FR-FT-001: Presigned single-part uploads

The API MUST provide presigned upload URLs for single-part uploads.

### FR-FT-002: Multipart workflow orchestration

The API MUST support multipart workflow endpoints for:

- initiate multipart upload
- sign part URLs
- complete multipart upload
- abort multipart upload

### FR-FT-003: Presigned download URLs

The API MUST provide presigned download URLs and support response-header overrides
(`Content-Disposition` and `Content-Type`) when appropriate.

### FR-FT-004: Object key safety rules

The API MUST enforce:

- server-generated keys only
- keys scoped to approved prefixes (`uploads/`, `exports/`, `tmp/`)

### FR-FT-005: Transfer Acceleration support

When configured, the API MUST support Transfer Acceleration in development and
production environments.

### FR-FT-006: Auth and authorization behavior

The API MUST:

- support JWT/OIDC verification when auth is enabled
- support same-origin/session-based scope derivation mode where required
- enforce authorization for upload/download operations by scope and policy

### NFR-FT-001: Security baseline

Storage MUST remain private by default; no public bucket/object policy exposure.

### NFR-FT-002: IAM least privilege

IAM policies MUST scope S3/KMS access to the required bucket resources and prefixes.

### NFR-FT-003: Scalability model

The API MUST handle large-file workflows without becoming a data-plane relay.

### NFR-FT-004: Reliability and cleanup

Incomplete multipart uploads MUST be cleaned up via S3 lifecycle configuration.

### NFR-FT-005: Observability

Structured logs and request correlation IDs MUST be present for operations and errors.

### NFR-FT-006: Env contract compatibility

Runtime configuration MUST remain aligned to container-craft injected
`FILE_TRANSFER_*` environment variables.

### NFR-FT-007: Documentation and contract automation

OpenAPI and API documentation publication MUST be automated in CI/CD and updated on
contract changes.

## Integration requirements

### IR-FT-001: container-craft S3 integration

Use container-craft `infra/file_transfer/s3.yml` bucket provisioning and injected
`FILE_TRANSFER_*` environment variables.

### IR-FT-002: container-craft deployment workflows

Deploy via container-craft run modes (for example `deploy-ecs-cluster`,
`deploy-new-service`, and related service rollout workflows).

### IR-FT-003: OpenAPI exposure for client generation

Expose OpenAPI schema artifacts for TypeScript code generation and R client generation.

## Explicit non-goals

### NG-FT-001: API data-plane streaming

Streaming upload/download bytes through this API service is out of scope.

### NG-FT-002: Cross-account multi-tenant federation

A shared cross-project multi-tenant API is out of scope unless introduced by a future
ADR.

### NG-FT-003: Default CloudFront provisioning

Default CloudFront distribution provisioning is out of scope (optional future work).
