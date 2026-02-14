# Requirements (nova runtime)

Status: Canonical requirements source
Last updated: 2026-02-13

This document is the source of truth for functional and non-functional
requirements for the first production release.

## Scope

The system is a FastAPI control-plane API for direct-to-S3 transfers. It returns
presigned URLs and upload/download metadata. It does not proxy file bytes.

Primary consumers:

- Same-origin sidecar web applications (default)
- Embedded Python apps through bridge integration
- Standalone API clients (beta support in initial release)

## Functional Requirements

### FR-0000: File-transfer control-plane endpoints

The service MUST provide:

- `POST /api/transfers/uploads/initiate`
- `POST /api/transfers/uploads/sign-parts`
- `POST /api/transfers/uploads/complete`
- `POST /api/transfers/uploads/abort`
- `POST /api/transfers/downloads/presign`

### FR-0001: Async job endpoints and orchestration

The service MUST provide:

- `POST /api/jobs/enqueue`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/cancel`
- `POST /api/jobs/{job_id}/result` (worker/internal update path)

The default async orchestration path MUST be SQS + ECS worker. Step
Functions/Lambda are out of scope for the initial release.

In same-origin mode, browser polling calls to `GET /api/jobs/{job_id}` and other
body-less scope-bound endpoints MUST include caller scope via trusted header
(`X-Session-Id` or `X-Scope-Id`). If both `X-Session-Id` and `X-Scope-Id` are
provided, `X-Session-Id` MUST take precedence and the server MUST ignore
`X-Scope-Id` for scope binding on those endpoints. Differing values between
those two headers MUST NOT be treated as a protocol error; the request MUST be
evaluated using `X-Session-Id` and return the normal endpoint response.

Enqueue failure semantics:

- Queue publish failure MUST return `503`.
- Queue publish failure MUST return `error.code = "queue_unavailable"`.
- Queue publish failure MUST transition created job records to `failed`.

Worker result-update semantics:

- Worker status updates MUST follow legal transitions:
  - `pending -> pending|running|succeeded|failed|canceled`
  - `running -> running|succeeded|failed|canceled`
  - terminal states (`succeeded|failed|canceled`) only allow same-state
    idempotent updates.
- Invalid status transitions MUST return `409` with `error.code = "conflict"`.

### FR-0002: Operational endpoints

The service MUST provide:

- `GET /healthz`
- `GET /readyz`
- `GET /metrics/summary`

Readiness evaluation MUST include only traffic-critical dependencies.
Feature flags (for example `JOBS_ENABLED`) MUST NOT drive readiness pass/fail.

### FR-0003: Key generation and scope enforcement

The service MUST:

- Generate keys server-side only.
- Enforce prefix and caller scope ownership for all follow-up operations.
- Reject client attempts to operate outside allowed prefixes.

### FR-0004: Idempotency for mutation entrypoints

`uploads/initiate` and `jobs/enqueue` MUST support idempotent retries using the
`Idempotency-Key` header.

Failed enqueue responses (`503 queue_unavailable`) MUST NOT be replay-cached as
successful idempotency entries.

The idempotency implementation MUST use an explicit request lifecycle:

- claim (`in_progress`) before mutation execution
- commit (`committed`) only after successful mutation response
- discard claims on failed mutation execution to preserve retry behavior

### FR-0005: Authentication and authorization

The service MUST support explicit auth modes:

- Same-origin mode
- Local JWT/OIDC verification mode (default for token mode)
- Optional remote auth API mode (fail-closed when enabled)

In JWT modes, trusted principal-derived scope MUST override any client-provided
session scope.

### FR-0006: Two-tier caching

The service MUST support a two-tier cache model:

- Local in-process TTL cache
- Shared Redis cache (optional, best-effort)

Shared cache keys MUST be namespaced and schema-versioned, and JWT cache TTL
MUST be bounded by token expiration (`exp`) with configured max TTL caps.

### FR-0007: Observability and analytics

The service MUST emit:

- Structured logs with `request_id`
- CloudWatch EMF-compatible metrics with bounded dimensions
- EMF payload objects emitted as top-level structured log fields (including
  `_aws`), not nested JSON strings
- Daily activity rollups (memory in local/dev, DynamoDB in AWS)
- Queue lag metric from worker processing (`jobs_queue_lag_ms`) when jobs first
  transition out of `pending`
- Worker result-update throughput counters (`jobs_worker_result_updates_total`
  and per-status counters)

For DynamoDB-backed rollups, `active_users_today` and `distinct_event_types`
MUST be incremented using first-seen marker logic with conditional writes.

### FR-0008: OpenAPI contract ownership

OpenAPI 3.1 output from the API implementation MUST be the canonical HTTP
contract source for docs and client generation.

### FR-0009: S3 multipart correctness and acceleration compatibility

The service MUST enforce AWS multipart constraints:

- part number range: 1 to 10,000
- part size bounds: 5 MiB to 5 GiB (last part may be smaller)
- complete payload includes per-part `ETag` values

When `FILE_TRANSFER_USE_ACCELERATE_ENDPOINT=true`, presigned URLs MUST be
generated using acceleration-compatible client configuration.

## Non-Functional Requirements

### NFR-0000: Security baseline

The service MUST:

- Never log presigned URLs, query signatures, or bearer tokens.
- Enforce strict JWT validation with issuer/audience/alg checks.
- Use least-privilege IAM for S3/SQS/DynamoDB/Redis integration.

### NFR-0001: Performance and event-loop safety

The service MUST avoid event-loop blocking for synchronous verification code.
Synchronous JWT verification in async paths MUST run behind a threadpool
boundary.

### NFR-0002: Scalability and resilience

The service MUST remain control-plane only and scale horizontally behind ALB on
ECS/Fargate.

Selected backend misconfiguration MUST fail fast at startup instead of silently
degrading behavior.

### NFR-0003: Operability

The service MUST support health/readiness checks, dashboarding, and alarms that
cover latency, error rate, and queue backlog.

### NFR-0004: CI/CD and quality gates

Every change MUST pass:

- `source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .`
- `source .venv/bin/activate && uv run mypy`
- `source .venv/bin/activate && uv run pytest -q`

## Integration Requirements

### IR-0000: container-craft env contract compatibility

Runtime settings MUST remain compatible with container-craft `FILE_TRANSFER_*`
environment injection.

### IR-0001: Sidecar routing model

Default deployment MUST use same-origin ALB path routing for
`/api/transfers/*` and `/api/jobs/*`.

### IR-0002: AWS service dependencies

Initial AWS dependencies include S3, ECS/Fargate, ALB, SQS, ElastiCache Redis,
DynamoDB, and CloudWatch.

### IR-0003: Optional remote auth service

When enabled, remote auth integration MUST target `nova-auth-api` and fail closed
on auth service errors.

### IR-0004: Browser compatibility for multipart workflows

S3 CORS policies MUST allow browser upload/download operations and expose
`ETag` for multipart completion flows.

## Explicit Non-Goals (Initial Release)

- Building a byte-streaming data-plane API.
- Introducing Step Functions/Lambda orchestration by default.
- Splitting into microservices beyond file-transfer API + optional auth API.
