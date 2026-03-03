# Requirements (nova runtime)

Status: Canonical requirements source
Last updated: 2026-03-03

This document is the source of truth for functional and non-functional
requirements for the first production release.

## Architecture State Model

- Current production-target requirements use the `FR-*`, `NFR-*`, and `IR-*`
  IDs below.
- Hard-cut route authority is active under `ADR-0023` + `SPEC-0016`.
- Runtime contract is canonical `/v1/*` plus `/metrics/summary`; legacy
  `/api/*`, `/healthz`, and `/readyz` are removed.

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

- `POST /v1/transfers/uploads/initiate`
- `POST /v1/transfers/uploads/sign-parts`
- `POST /v1/transfers/uploads/complete`
- `POST /v1/transfers/uploads/abort`
- `POST /v1/transfers/downloads/presign`

### FR-0001: Async job endpoints and orchestration

The service MUST provide:

- `POST /v1/jobs`
- `GET /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `POST /v1/jobs/{job_id}/cancel`
- `POST /v1/jobs/{job_id}/retry`
- `GET /v1/jobs/{job_id}/events`
- `POST /v1/internal/jobs/{job_id}/result` (worker/internal update path)

The default async orchestration path MUST be SQS + ECS worker. Step
Functions/Lambda are out of scope for the initial release.

In same-origin mode, all scope binding follows header precedence:

- `X-Session-Id` has precedence over `X-Scope-Id`.
- If both headers are present, `X-Scope-Id` is ignored for scope binding.

Body-less scope-bound endpoints (for example polling calls like
`GET /v1/jobs/{job_id}`) MUST evaluate scope only from headers:

- These endpoints MUST use `X-Session-Id` and may use `X-Scope-Id` only as the fallback
  when `X-Session-Id` is absent.
- Header-only scope resolution for these endpoints MUST use:
  - `session_scope = X-Session-Id` if provided and non-blank;
  - otherwise `session_scope = X-Scope-Id`.
- Differing values between `X-Session-Id` and `X-Scope-Id` MUST NOT be treated as
  an error.

Body-carrying scope-bound endpoints (requests with request body field `session_id`)
MUST validate body-to-header consistency using the same header names:

- `session_id` in request body MUST be compared to `X-Session-Id` first when both are present.
- If both `X-Session-Id` and body `session_id` are present but different, the request MUST fail with
  `422` and `error.message = "conflicting session scope"`.
- If `X-Session-Id` is absent, but both `X-Scope-Id` and body `session_id` are present
  but different, the request MUST fail with
  `401` and `error.message = "conflicting session scope"`.

Enqueue failure semantics for `POST /v1/jobs`:

- On queue publish failure:
  - Return HTTP `503` with `error.code = "queue_unavailable"`.
  - Transition any created job records to `failed`.
- In-memory queue mode MUST honor `process_immediately`; when disabled, enqueue
  returns a `pending` job and MUST NOT auto-transition to `succeeded`.

Worker result-update semantics:

- Worker status updates MUST follow legal transitions:
  - `pending -> pending|running|succeeded|failed|canceled`
    (`pending -> succeeded` is allowed for atomic worker completion across
    backends; in-memory `process_immediately` simulation currently transitions
    through `running` before `succeeded`)
  - `running -> running|succeeded|failed|canceled`
  - terminal states (`succeeded|failed|canceled`) only allow same-state
    idempotent updates.
- Worker updates that set `status = succeeded` MUST clear `error` to `null`.
- Invalid status transitions MUST return `409` with `error.code = "conflict"`.

### FR-0002: Operational endpoints

The service MUST provide:

- `GET /v1/health/live`
- `GET /v1/health/ready`
- `GET /metrics/summary`

Readiness evaluation MUST include only traffic-critical dependencies.
Feature flags (for example `JOBS_ENABLED`) MUST NOT drive readiness pass/fail.

- Missing or blank `FILE_TRANSFER_BUCKET` MUST fail readiness.

### FR-0003: Key generation and scope enforcement

The service MUST:

- Generate keys server-side only.
- Enforce prefix and caller scope ownership for all follow-up operations.
- Reject client attempts to operate outside allowed prefixes.

### FR-0004: Idempotency for mutation entrypoints

`uploads/initiate` and `jobs` create MUST support idempotent retries using the
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

### FR-0010: Route hard-cut guardrails

The hard-cut route policy MUST enforce:

- no runtime reintroduction of `/api/*`, `/healthz`, or `/readyz`
- no `/api/v1/*` namespace aliases
- OpenAPI path set constrained to `/v1/*` plus `/metrics/summary`
- route decorator checks across runtime route-definition modules (including
  router modules mounted via `include_router`) resolving only to allowed
  runtime paths

## Non-Functional Requirements

### NFR-0000: Security baseline

The service MUST:

- Never log presigned URLs, query signatures, or bearer tokens.
- Enforce strict JWT validation with issuer/audience/alg checks.
- Use least-privilege IAM for S3/SQS/DynamoDB/Redis integration.
- Emit `WWW-Authenticate: Bearer ...` on JWT/OIDC `401` responses per RFC
  6750; header generation failures MUST fail closed by surfacing an auth error
  or using a deterministic secure fallback challenge.

### NFR-0001: Performance and event-loop safety

The service MUST avoid event-loop blocking for synchronous verification code.
Synchronous JWT verification in async paths MUST run behind a threadpool
boundary.
Threadpool offloads for synchronous JWT verification MUST use an explicit
concurrency limiter (for example, semaphore or AnyIO/Starlette
`CapacityLimiter`) with a default cap of 40 tokens unless measured resource
limits require adjustment.

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

- `source .venv/bin/activate && uv lock --check`
- `source .venv/bin/activate && uv run ruff check . --fix`
- `source .venv/bin/activate && uv run ruff check . --select I`
- `source .venv/bin/activate && uv run ruff format .`
- `source .venv/bin/activate && uv run mypy`
- `source .venv/bin/activate && uv run pytest -q`
- `source .venv/bin/activate && uv run pytest -q packages/nova_file_api/tests/test_generated_client_smoke.py`
- workspace package/app build verification (`uv build` per workspace unit)

### NFR-0105: Contract traceability

Target implementation PRs MUST update `README.md`, `AGENTS.md`,
`docs/PRD.md`, `docs/architecture/requirements.md`, affected ADR/SPEC docs,
and `docs/plan/PLAN.md` in the same change set. Historical pointer files
(`PRD.md`, `FINAL-PLAN.md`) MUST be updated only when archive location or
authority links change.

### NFR-0106: No-shim posture

Route and contract changes MUST not introduce compatibility aliases or
namespace shims unless ADR-approved with score >=9.0.

## Integration Requirements

### IR-0000: Nova-local runtime and release authority

Active runtime and release/deploy infrastructure authority MUST remain in this
repository under `infra/nova/**` and `infra/runtime/**`.

### IR-0001: Sidecar routing model

Default deployment MUST use same-origin ALB path routing for canonical `/v1/*`
runtime surfaces.

### IR-0002: AWS service dependencies

Initial AWS dependencies include S3, ECS/Fargate, ALB, SQS, ElastiCache Redis,
DynamoDB, and CloudWatch.

### IR-0003: Optional remote auth service

When enabled, remote auth integration MUST target `nova-auth-api` and fail closed
on auth service errors.

### IR-0004: Browser compatibility for multipart workflows

S3 CORS policies MUST allow browser upload/download operations and expose
`ETag` for multipart completion flows.

### IR-0010: Historical migration scope

Historical migration evidence under `docs/history/**` MUST remain non-authoritative
for current runtime and deployment operations.

## Explicit Non-Goals (Initial Release)

- Building a byte-streaming data-plane API.
- Introducing Step Functions/Lambda orchestration by default.
- Splitting into microservices beyond file-transfer API + optional auth API.
