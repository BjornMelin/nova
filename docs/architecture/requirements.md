# Requirements (nova runtime)

Status: Canonical requirements source
Last updated: 2026-03-02

This document is the source of truth for functional and non-functional
requirements for the first production release.

## Architecture State Model

- Current implemented baseline requirements use the `FR-*`, `NFR-*`, and
  `IR-*` IDs below.
- Target-state requirements for the next implementation branch use
  `TFR-*`, `TNFR-*`, and `TIR-*` IDs and are derived from `ADR-0015` and
  `SPEC-0015`.
- Until target-state code is merged, baseline IDs remain operational authority.

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
If both `X-Session-Id` and body `session_id` are present but do not match, the
request MUST fail with `422` and `error.message = "conflicting session scope"`.
If `X-Session-Id` is absent and `X-Scope-Id` plus body `session_id` are both
present but do not match, the request MUST fail with `401` and
`error.message = "conflicting session scope"`.

Enqueue failure semantics:

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

- `GET /healthz`
- `GET /readyz`
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

## Target-State Functional Requirements (Planned)

### TFR-0100: API capability endpoint contract

The next feature branch MUST expose:

- `GET|POST /v1/jobs` capability surface (create/list/get/cancel/retry)
- `GET /v1/jobs/{id}/events` (poll/SSE-capable event stream surface)
- `GET /v1/capabilities`
- `POST /v1/resources/plan`
- `GET /v1/releases/info`
- `GET /v1/health/live`
- `GET /v1/health/ready`

### TFR-0101: Target workflow artifact completion set

The next feature branch MUST bring the remaining `SPEC-0015` workflow artifact
set to contract-complete behavior:

- `build-and-publish-image.yml`
- `deploy-dev.yml`
- `post-deploy-validate.yml`
- `conformance-clients.yml`

These workflows already exist in `.github/workflows/`; required work is to
close behavior gaps against `SPEC-0015`, not to introduce new filenames.

Implemented baseline artifacts already contract-complete in `main`:

- `ci.yml`
- `publish-packages.yml`
- `promote-prod.yml`

### TFR-0102: No-shim cutover posture

Target-state contract migration MUST not introduce compatibility alias routes,
retired namespaces, or transitional wrappers unless explicitly approved by a
new ADR.

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

## Target-State Non-Functional Requirements (Planned)

### TNFR-0100: Target-state contract traceability

Target implementation PRs MUST update `README.md`, `PRD.md`, `AGENTS.md`,
`docs/architecture/requirements.md`, affected ADR/SPEC docs, and
`FINAL-PLAN.md`/`docs/plan/PLAN.md` in the same change set.

### TNFR-0101: Baseline operability preservation during transition

Until target-state routes are implemented, current baseline operational docs
and runbooks MUST remain executable and clearly labeled as baseline behavior.

## Integration Requirements

<a id="ir-0000-container-craft-env-contract-compatibility"></a>

### IR-0000: Legacy container-craft env contract compatibility (transitional)

Runtime settings MAY retain compatibility with historical
`container-craft` `FILE_TRANSFER_*` environment injection during migration, but
active deployment authority is Nova-local (`infra/nova/**`, `infra/runtime/**`).

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

## Target-State Integration Requirements (Planned)

### TIR-0100: Nova-local IaC authority

Active runtime and release/deploy infrastructure authority MUST remain in this
repository under `infra/nova/**` and `infra/runtime/**`.

## Explicit Non-Goals (Initial Release)

- Building a byte-streaming data-plane API.
- Introducing Step Functions/Lambda orchestration by default.
- Splitting into microservices beyond file-transfer API + optional auth API.
