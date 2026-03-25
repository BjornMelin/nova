# Requirements (nova runtime)

Status: Canonical requirements source
Last updated: 2026-03-22

This document is the source of truth for functional and non-functional
requirements for the first production release.

## Architecture State Model

- Current production-target requirements use the `FR-*`, `NFR-*`, `IR-*`, and
  `GFR-*` IDs below.
- Hard-cut **path** authority is active under `ADR-0023` + `SPEC-0016`; public
  **auth and worker persistence** target state is under `ADR-0033` through
  `ADR-0041`, `SPEC-0027` through `SPEC-0029`, and the
  [green-field program](../plan/greenfield-simplification-program.md).
- Runtime URL namespace is canonical `/v1/*` plus `/metrics/summary`; non-canonical
  route families are removed. “Contract revision” in `SPEC-0027` refers to auth
  and OpenAPI expression, not a `/v2/*` prefix unless a future ADR introduces it.
- Runtime API, runtime package ownership, runtime safety, and downstream
  validation authority are synchronized under `ADR-0024`, with runtime
  component/safety governance codified in `ADR-0025`, `ADR-0026`,
  `SPEC-0017`, `SPEC-0018`, and `SPEC-0019`, and downstream validation
  contracts codified in `ADR-0027` through `ADR-0029` and `SPEC-0021` through
  `SPEC-0023`.
- Shared request-context propagation, request-id parity, and canonical FastAPI
  exception registration are owned by `nova_runtime_support` via the `ADR-0041`
  transport cut and reused by FastAPI app factories.
- Adjacent deploy-governance authority is isolated under `ADR-0030` through
  `ADR-0032` and `SPEC-0024` through `SPEC-0026`.
- Superseded ADR/SPEC material is archived only under
  `docs/architecture/adr/superseded/**` and
  `docs/architecture/spec/superseded/**` (for example superseded `ADR-0005` and
  `SPEC-0007`).
- Public SDK policy: Python public; TypeScript release-grade in CodeArtifact
  (generator-owned, subpath-only, `openapi-typescript` + `openapi-fetch` stack
  per `ADR-0038` / `SPEC-0029`, with the active workspace kept on the verified
  TypeScript 5.x line while TypeScript 6 remains deferred); R first-class
  internal release line (`httr2` thin client per `ADR-0038` / `SPEC-0029`).

## Green-field program requirements (GFR)

Normative statements that drive the
[green-field simplification program](../plan/greenfield-simplification-program.md).
See also [greenfield-authority-map.md](../plan/greenfield-authority-map.md).

### GFR-R1 — Single public runtime authority

Nova MUST expose one canonical public API runtime. There MUST NOT be a separate
auth microservice in the target architecture.

### GFR-R2 — Auth context comes from verified claims

Public caller scope, tenant, and permissions MUST be derived from verified JWT
claims rather than from request-body or custom-header surrogates (`session_id`,
`X-Session-Id`, `X-Scope-Id`).

### GFR-R3 — Async correctness is mandatory

The API and worker MUST NOT rely on blocking auth or transport operations on
async event-loop paths when async-native alternatives exist.

### GFR-R4 — Public contract must be explicit

Typed request/response models and a stable public OpenAPI artifact remain
required.

### GFR-R5 — Worker must not self-call the API

Worker completion and result updates MUST happen through shared code or direct
persistence primitives, not HTTP callbacks into the API runtime.

### GFR-R6 — SDKs must feel native per language

Python, TypeScript, and R SDKs MUST follow the stacks in `ADR-0038` /
`SPEC-0029` and active `SPEC-0012` conformance rules. Superseded `SPEC-0011` is
indexed in [`spec/index.md`](./spec/index.md) (Superseded) for traceability
only—not implementation authority.

For the current public file API contract, the R SDK MUST remain a thin `httr2`
package with concrete OpenAPI parameter signatures, bearer-token auth, and
JSON request/response handling aligned to the declared public media types.

### GFR-R7 — Managed AWS services preferred

Use managed AWS services when they reduce operational burden without violating
workload needs (`ADR-0039`).

### GFR-R8 — One client artifact family per language

There MUST NOT be auth-only SDK families in the target architecture.

### GFR-R9 — Deterministic build and verification

The repository MUST remain reproducible with `uv`, Ruff, mypy/pytest/`ty`, and
language-specific SDK checks.

### GFR-R10 — Repo should shrink after every accepted branch

Every green-field branch SHOULD delete obsolete artifacts or enable later
deletions; the program completes with a full repo rebaseline (`ADR-0040`).

## Scope

The system is a FastAPI control-plane API for direct-to-S3 transfers. It returns
presigned URLs and upload/download metadata. It does not proxy file bytes.

Primary consumers:

- Browser and server clients using bearer JWT against the public file API
- Embedded Python apps through bridge integration (`nova_dash_bridge`), where
  FastAPI hosts consume the async-first `nova_file_api.public` seam directly
  and sync-only hosts use explicit edge adapters
- Standalone API clients

## Functional Requirements

### FR-0000: File-transfer control-plane endpoints

The service MUST provide:

- `POST /v1/transfers/uploads/initiate`
- `POST /v1/transfers/uploads/sign-parts`
- `POST /v1/transfers/uploads/introspect`
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

Worker completion and terminal job updates MUST use the **direct persistence**
path (`SPEC-0028`, `ADR-0035`). There MUST NOT be a worker → API HTTP callback
for job results in the target architecture.

The default async orchestration path MUST be SQS + ECS worker. Step
Functions/Lambda are out of scope for the initial release.

Scope binding for job endpoints MUST follow verified **JWT claims** in the
public file API (`SPEC-0027`, `GFR-R2`). `session_id`, `X-Session-Id`, and
`X-Scope-Id` MUST NOT be used as public authorization scope carriers.

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

Readiness evaluation MUST expose the current runtime dependency checks (as required by
FR-0002 and the Readiness evaluation clause) and MUST return `503 Service
Unavailable` when any traffic-critical check is false. This HTTP 503 signal is the
canonical readiness-failure behavior across runtime, tests, and docs.
Feature flags (for example `JOBS_ENABLED`) MUST NOT drive readiness pass/fail
by themselves; disabled features collapse to ready checks instead of
introducing failing dependencies.

- Missing or blank `FILE_TRANSFER_BUCKET` MUST fail readiness.
- `AUTH_MODE=jwt_local` with missing `OIDC_ISSUER`, `OIDC_AUDIENCE`, or
  `OIDC_JWKS_URL` MUST fail the dedicated `auth_dependency` readiness check on
  `/v1/health/ready`.

### FR-0003: Key generation and scope enforcement

The service MUST:

- Generate keys server-side only.
- Enforce prefix and caller scope ownership for all follow-up operations.
- Reject client attempts to operate outside allowed prefixes.

### FR-0004: Idempotency for mutation entrypoints

`POST /v1/transfers/uploads/initiate` and `POST /v1/jobs` create endpoints MUST
support idempotent retries using the `Idempotency-Key` header.

Failed enqueue responses (`503 queue_unavailable`) MUST NOT be replay-cached as
successful idempotency entries.

The idempotency implementation MUST use an explicit request lifecycle:

- claim (`in_progress`) before mutation execution
- commit (`committed`) only after successful mutation response
- discard claims on failed mutation execution to preserve retry behavior

Current runtime posture:

- `IDEMPOTENCY_ENABLED` and `IDEMPOTENCY_TTL_SECONDS` are the active
  configuration surface; the runtime does not expose `IDEMPOTENCY_MODE`.
- `IDEMPOTENCY_ENABLED=true` requires `CACHE_REDIS_URL` and a shared Redis
  claim store for duplicate prevention across instances.
- Shared idempotency store failures MUST fail closed with `503` and
  `error.code = "idempotency_unavailable"`.
- If a mutation succeeds but the replay record cannot be committed, Nova MUST
  preserve the existing `in_progress` claim so retries with the same key do
  not execute the mutation a second time.
- Clients receiving `idempotency_unavailable` from a protected mutation MUST
  reuse the same `Idempotency-Key`; minting a new key after that response risks
  creating a duplicate mutation.
- Missing `Idempotency-Key` remains allowed; blank keys are invalid.
- Active operator docs and deploy automation MUST enforce the shared-cache
  requirement without introducing a mode matrix.

### FR-0005: Authentication and authorization

The service MUST authenticate public callers with **bearer JWT** and MUST derive
scope, tenant, and permissions from **verified claims** in the file API runtime
(`ADR-0033`, `ADR-0034`, `SPEC-0027`, `GFR-R2`).

There MUST NOT be a separate `nova-auth-api` HTTP surface or auth-only SDK
families in the target architecture.

### FR-0006: Two-tier caching

The service MUST support a two-tier cache model:

- Local in-process TTL cache
- Shared Redis cache used as the distributed cache tier when
  `CACHE_REDIS_URL` is configured

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
contract source for docs and client generation (`ADR-0002`, `ADR-0036`).

Runtime OpenAPI metadata MUST follow these rules:

- `operationId` values are unique, stable, and snake_case-aligned to the
  runtime OpenAPI contract tests.
- Public operation tags are semantic group tags only (`transfers`, `jobs`,
  `platform`, `ops`, and `health`); the dedicated `token` tag family is retired
  with the auth service surface.
- Bearer security schemes MUST be expressed with FastAPI security dependencies
  so emitted OpenAPI matches runtime behavior (`SPEC-0027`).
- Custom request-body schema references emitted via OpenAPI overrides MUST
  resolve to named component schemas in the same document and remain contract-
  test verifiable from runtime OpenAPI output.
- Post-generation schema mutation MUST be minimal (`ADR-0036`).

### FR-0009: S3 multipart correctness and acceleration compatibility

The service MUST enforce AWS multipart constraints:

- part number range: 1 to 10,000
- part size bounds: 5 MiB to 5 GiB (last part may be smaller)
- complete payload includes per-part `ETag` values
- `POST /v1/transfers/uploads/introspect` MUST expose uploaded part state
  for resumable multipart uploads
- default runtime posture MUST support `500 GiB` single-file uploads through
  `FILE_TRANSFER_MAX_UPLOAD_BYTES=536_870_912_000`, while remaining
  environment-configurable upward
- default upload presign TTL MUST be `1800` seconds
- browser and bridge clients MUST use progressive multipart signing rather than
  wide-batch presigning; the canonical batch rule is
  `min(16, 2 * maxConcurrency)` unless a smaller client override is configured
- export-copy flows for objects larger than `5 GB` MUST use multipart copy
  rather than `CopyObject`

When `FILE_TRANSFER_USE_ACCELERATE_ENDPOINT=true`, presigned URLs MUST be
generated using acceleration-compatible client configuration.

### FR-0010: Route hard-cut guardrails

The hard-cut route policy MUST enforce:

- no runtime reintroduction of non-canonical route families
- no alternate namespace aliases outside canonical `/v1/*`
- OpenAPI path set constrained to `/v1/*` plus `/metrics/summary`
- route decorator checks across runtime route-definition modules (including
  router modules mounted via `include_router`) resolving only to allowed
  runtime paths

### FR-0011: Downstream hard-cut consumer integration contract

Downstream consumer repositories and integration examples MUST:

- use canonical `/v1/transfers` and `/v1/jobs` route families only
- use reusable post-deploy validation contracts that assert canonical
  non-`404` behavior
- assert explicit legacy route `404` behavior for removed routes
- keep workflow pinning policy explicit (`@v1` stable, `@v1.x.y`/SHA immutable)

### FR-0012: Auth0 tenant ops reusable workflow contract

Auth0 tenant operations MUST be governed by reusable workflow API contracts with
typed input/output schemas and safety controls aligned with local
tenant-as-code validator behavior.
Import/export mutation paths MUST hard-fail before mutation when
`validate_auth0_contract` fails.

### FR-0013: SSM runtime base URL authority for deploy validation

Deploy validation base URLs MUST be sourced from SSM-backed authority values
using environment-scoped parameter paths and passed into validation workflows as
HTTPS values. These parameter paths MUST be owned by a single canonical stack
pair (`${PROJECT}-ci-dev-service-base-url`,
`${PROJECT}-ci-prod-service-base-url`) with no overlapping stack ownership.

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

The service MUST avoid event-loop blocking for synchronous work on async
handlers.

JWT verification SHOULD be **async-native** in the file API when implemented
(`ADR-0033`, `ADR-0037`). Any **remaining** synchronous verification or
cryptographic work on async paths MUST run behind a threadpool boundary with an
explicit concurrency limiter (for example, semaphore or AnyIO/Starlette
`CapacityLimiter`) with a default cap of 40 tokens unless measured resource
limits require adjustment (`ADR-0026`, `SPEC-0019`).
FastAPI transfer routes MUST consume the async-first public seam directly
instead of round-tripping through a sync bridge façade; any retained sync
adapters stay scoped to true sync framework edges.

### NFR-0002: Scalability and resilience

The service MUST remain control-plane only and scale horizontally behind a
CloudFront + WAF public edge, with an internal ALB origin and ECS/Fargate API
and worker services.

Default runtime posture MUST support `500 GiB` single-file uploads and
multi-TiB aggregate workloads through direct-to-S3 multipart transfer, not API
byte proxying.

Selected backend misconfiguration MUST fail fast at startup instead of silently
degrading behavior.

### NFR-0003: Operability

The service MUST support health/readiness checks, dashboarding, and alarms that
cover latency, error rate, and queue backlog.

### NFR-0004: CI/CD and quality gates

Nova MUST keep the following canonical verification baseline current and
documented. Changes MUST pass the applicable baseline subset plus any
touched-surface add-on gates from `AGENTS.md` and
`docs/standards/repository-engineering-standards.md`:

- `uv sync --locked --all-packages --all-extras --dev`
- `uv lock --check`
- `uv run ruff check .`
- `uv run ruff check . --select I`
- `uv run ruff format . --check`
- `uv run ty check --force-exclude --error-on-warning packages scripts`
- `uv run mypy`
- `uv run pytest -q`
- `uv run pytest -q packages/nova_file_api/tests/test_generated_client_smoke.py`
- `uv run python scripts/contracts/export_openapi.py --check`
- `uv run python scripts/release/generate_runtime_config_contract.py --check`
- `uv run python scripts/release/generate_clients.py --check`
- `uv run python scripts/release/generate_python_clients.py --check`
- workspace package/app build verification (`uv build` per workspace unit)

The canonical typing gates are
`uv run ty check --force-exclude --error-on-warning packages scripts`
and `uv run mypy`. `ty` is the required full-repo gate; `mypy` remains the
required compatibility backstop in this phase. The primary quality/generation
lane runs on Python 3.13 (`quality-gates`). Workspace packages support Python
3.11+, and `python-compatibility` retains Python 3.11 plus 3.12 pytest/build
coverage for surviving packages.

### NFR-0105: Contract traceability

Target implementation PRs MUST update the current canonical routers and any
affected authority docs in the same change set. The exact router set is owned
by `docs/standards/repository-engineering-standards.md`. Historical artifacts
under `docs/history/**` MUST be updated only when archive location or authority
links change.

### NFR-0106: No-shim posture

Route and contract changes MUST not introduce compatibility aliases or
namespace shims unless ADR-approved with score >=9.0.

### NFR-0107: Downstream contract-doc and schema synchronization

Changes to downstream integration contracts MUST update all affected workflow
schema files in `docs/contracts/**`, consumer integration docs in
`docs/clients/**`, and enforcing infra/docs tests in the same change set.

### NFR-0108: Auth0 workflow contract synchronization

Changes to Auth0 tenant operation contracts MUST keep runbook guidance,
reusable workflow schema contracts, and `validate_auth0_contract` checks
synchronized in one PR.

### NFR-0109: Runtime base URL integrity and provenance

Dev/prod validation base URLs MUST be HTTPS, environment-scoped, and sourced
from SSM authority values with evidence captured in release runbooks.

### NFR-0110: Architecture authority synchronization

Active architecture docs, indexes, and operator instruction files MUST remain
synchronized and truthfully describe the subject identified by each active
ADR/SPEC identifier.

## Integration Requirements

### IR-0000: Nova-local runtime and release authority

Active runtime and release/deploy infrastructure authority MUST remain in this
repository under `infra/nova/**` and `infra/runtime/**`.

### IR-0001: Sidecar routing model

Default deployment MUST use a public CloudFront + WAF edge with an internal ALB
origin for canonical `/v1/*` runtime surfaces.

### IR-0002: AWS service dependencies

Initial AWS dependencies include S3, ECS/Fargate, ALB, SQS, ElastiCache Redis,
DynamoDB, and CloudWatch.

### IR-0003: Auth execution locality

JWT verification and principal normalization MUST run in the **public file API**
process (`ADR-0033`). Remote HTTP calls to a dedicated auth microservice are
**not** part of the target architecture (superseded `ADR-0005` /
`SPEC-0007`).

### IR-0004: Browser compatibility for multipart workflows

S3 CORS policies MUST allow browser upload/download operations and expose
`ETag` for multipart completion flows.

### IR-0010: Historical migration scope

Historical migration evidence under `docs/history/**` MUST remain non-authoritative
for current runtime and deployment operations.

### IR-0011: Cross-repo consumer conformance authority

Cross-repo consumer conformance for dash/rshiny/react-next integration remains
release-blocking authority, with canonical route usage and workflow contract
parity enforced by CI checks.

### IR-0012: Auth0 tenant ops authority boundary

Active Auth0 authority remains in-repo under `infra/auth0/**` with contract
schemas and validator checks; no external runtime repo owns active Auth0 tenant
ops contract behavior.

### IR-0013: SSM base URL source of truth for release validation

Deploy validation base URLs for dev/prod are sourced from SSM authority paths
and consumed by runbook/operator workflows as canonical source values.

### IR-0014: Superseded architecture archive boundary

Superseded ADR/SPEC content MUST live only under the dedicated
`docs/architecture/*/superseded/` directories and MUST NOT appear in active
authority lists or active catalog sections.

## Explicit Non-Goals (Initial Release)

- Building a byte-streaming data-plane API.
- Introducing Step Functions/Lambda orchestration by default.
- A separate auth microservice or parallel session/header authorization channel
  for public scope binding (`GFR-R1`, `GFR-R2`).
