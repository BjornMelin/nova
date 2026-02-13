# Final Production Architecture Plan (Locked, Release Track)

Status: Active execution
Last updated: 2026-02-12
Owner: nova program

## Summary

Deliver a complete first production release for:

- file-transfer control-plane API (FastAPI, sidecar-first)
- hardened JWT/OIDC verification
- async background processing capabilities (no workflow-engine bloat)
- two-tier caching with idempotency safety
- observability, dashboards, and activity analytics
- clear runtime versus infra ownership

## Locked Decisions

1. Repo topology: hybrid monorepo runtime + separate infra repo
   (`container-craft`) - Score: 9.6/10
2. Primary runtime: sidecar API behind same-origin ALB path routing -
   Score: 9.6/10
3. Runtime support levels: sidecar GA, embedded bridge migration path,
   standalone beta - Score: 9.5/10
4. Async orchestration: SQS + ECS worker (no Step Functions/Lambda at launch)
   - Score: 9.0/10
5. Analytics: EMF + CloudWatch alarms/dashboards + DynamoDB daily rollups -
   Score: 9.5/10
6. Cache: two-tier (local TTL + shared Redis) - Score: 9.4/10
7. Auth: local JWT verification default, optional remote auth mode fail-closed
   - Score: 9.3/10

## Anti-Entropy Principle

- API control-plane logic remains centralized in the runtime service.
- `nova-dash-bridge` remains an adapter and migration bridge package.
- Infra remains in `container-craft`; no duplicate IaC in runtime packages.
- Step Functions/Lambda stay out of initial release unless new ADR approves.

## Target End-State Architecture

### Runtime monorepo scope

Canonical runtime tree includes:

- `nova-file-api` service package (FastAPI)
- `nova-dash-bridge` bridge package (adapter/migration layer)
- `nova-auth-api` service package for optional remote auth mode
- shared OpenAPI artifacts, contracts, and test utilities

### Infra scope (`container-craft`)

- ECS/Fargate + ALB sidecar routing
- S3 + SQS + Redis + DynamoDB wiring
- CloudWatch dashboards and alarms
- least-privilege IAM resource policies

### Deployment shape (production)

- same-origin sidecar routing for `/api/transfers/*` and `/api/jobs/*`
- direct browser data-plane to S3 (API is control-plane only)
- SQS queue + ECS worker for async execution
- Redis for shared cache hot keys
- DynamoDB for daily activity rollups and durable job state

## Public APIs, Interfaces, and Contract Rules

### A. File-transfer control-plane endpoints

- `POST /api/transfers/uploads/initiate`
- `POST /api/transfers/uploads/sign-parts`
- `POST /api/transfers/uploads/complete`
- `POST /api/transfers/uploads/abort`
- `POST /api/transfers/downloads/presign`

### B. Async job endpoints

- `POST /api/jobs/enqueue`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/cancel`
- `POST /api/jobs/{job_id}/result`

### C. Operational endpoints

- `GET /healthz`
- `GET /readyz`
- `GET /metrics/summary`

### D. Contract requirements

- OpenAPI 3.1 is the canonical contract source.
- Standard error envelope:
  - `error.code`
  - `error.message`
  - `error.details`
  - `error.request_id`
- `X-Request-Id` propagates end-to-end.
- `Idempotency-Key` required on mutation entrypoints when enabled.
- Queue publish failures for `jobs/enqueue` return `503` with
  `error.code = "queue_unavailable"`.
- Failed enqueue responses are never replay-cached as successful idempotency
  results.
- Readiness pass/fail excludes feature-flag state (`jobs_enabled`).

## Security and Auth Finalization

- Canonical verifier: `oidc-jwt-verifier`
- Sync verification stays behind a threadpool boundary in async dependencies.
- Strict JWT rules: alg allowlist, iss/aud/exp/nbf, dangerous-header rejection
- Principal-derived scope overrides client-provided session scope in JWT modes.
- No logging of presigned URLs, JWTs, or signature query values.
- Remote auth mode remains explicit and fail-closed.

## Caching Finalization

- Tier 1 local TTL cache for hot-path metadata and verifier results.
- Tier 2 shared Redis cache for cross-instance acceleration.
- Shared cache stores include:
  - JWKS/auth metadata hot keys
  - idempotency replay keys
  - short-lived job lookup accelerators
- Redis outage must degrade to local-only mode without data leakage.

## Observability and Analytics Finalization

- Structured logs include: `request_id`, `route`, `auth_mode`, `outcome`,
  latency.
- EMF metrics include: requests, errors, auth failures, presign latency,
  enqueue latency, queue lag.
- Metric dimensions must stay bounded (no `user_id` high-cardinality labels).
- Daily activity rollups provide DAU/MAU-style and operation trend views.
- DynamoDB rollups use conditional marker writes so `active_users_today` and
  `distinct_event_types` remain accurate under concurrency.

## AWS Infra Requirements (`container-craft`)

- Preserve `file_transfer_enabled` and canonical `FILE_TRANSFER_*` env contract.
- Add Redis/SQS/DynamoDB toggles and env mappings for runtime services.
- Preserve ALB sidecar routing for `/api/transfers/*` and `/api/jobs/*`.
- Tune health checks per ECS guidance (interval, threshold, startup grace).
- Use least-privilege IAM for S3/KMS/SQS/DynamoDB/Redis paths.

## Testing and Acceptance Scenarios

1. Contract: OpenAPI diff checks, schema validation, generated client smoke.
2. Auth/security: invalid issuer/audience/exp, insufficient scope, safe logs.
3. Async: enqueue -> worker -> completion, retries, idempotency, cancellation.
4. Caching: local hit/miss, Redis outage fallback, stale refresh behavior.
5. Observability: EMF dimensions bounded, dashboard population, alarm tests.
6. Performance/resilience: concurrent presign load and queue pressure behavior.

## Execution Sequence (GA Required)

1. Runtime monorepo consolidation and scaffolding.
2. File-transfer API core and OpenAPI hardening.
3. Auth finalization (`oidc-jwt-verifier` + threadpool boundary).
4. Async jobs endpoints plus SQS/ECS worker path.
5. Two-tier cache integration (local + Redis).
6. EMF instrumentation, rollups, dashboards, and alarms.
7. `container-craft` wiring for Redis/SQS/DynamoDB and validations.
8. Embedded bridge compatibility and migration docs.
9. Full E2E verification gates and release readiness.

## Execution Phases and Checklist Status

### Phase 1: Runtime foundation and contract hardening

- [x] Create FastAPI service skeleton and domain models
- [x] Implement transfer endpoints and S3 orchestration service
- [x] Implement error envelope and request-id middleware
- [x] Implement local JWT and remote auth mode wiring
- [x] Add idempotency replay handling for initiate and enqueue
- [x] Add baseline health/readiness/metrics endpoints
- [x] Add initial unit/integration tests for health and idempotency

### Phase 2: Async jobs, cache, and observability hardening

- [x] Add async job API handlers and queue abstractions
- [x] Add two-tier cache primitives (local + Redis)
- [x] Add activity rollup backends (memory + DynamoDB)
- [x] Add EMF metric emission helper and request logging hardening
- [x] Remediate enqueue publish failure propagation (`503 queue_unavailable`)
- [x] Remediate readiness false negatives from feature flags
- [x] Remediate DynamoDB distinct event-type rollup counting
- [x] Add fail-fast validation for selected SQS/DynamoDB backends
- [x] Add durable job repository backend for AWS deployments (DynamoDB)
- [x] Add explicit queue lag metric integration from worker processing

### Phase 3: Architecture docs alignment

- [x] Update requirements to final architecture decisions
- [x] Add ADRs for async orchestration, cache/idempotency, runtime support,
  and observability stack
- [x] Add SPECs for async jobs, caching/idempotency, and rollup analytics
- [x] Update spec/adr indexes and references
- [x] Rewrite subplans and trigger prompts for final execution model
- [x] Refresh README, PRD, and AGENTS guidance with implementation semantics

### Phase 4: Cross-repo integration and release closure

- [x] Align `container-craft` IaC for Redis/SQS/DynamoDB toggles and env mapping
- [ ] Validate sidecar ALB routing and health-check tuning in non-prod
- [x] Validate SQS worker path (enqueue -> execute -> status transition)
- [ ] Validate CloudWatch dashboards and alarms with synthetic failures
- [x] Finalize migration bridge docs and standalone beta smoke coverage
- [x] Complete release checklist and versioning across participating repos

External live gate execution reference:

- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`

## Subplan Mapping

- `docs/plan/subplans/SUBPLAN-0001.md`: core runtime and contract hardening
- `docs/plan/subplans/SUBPLAN-0002.md`: async, cache, and observability
- `docs/plan/subplans/SUBPLAN-0003.md`: infra and cross-repo integration
- `docs/plan/subplans/SUBPLAN-0004.md`: E2E validation and release closure
- `docs/plan/subplans/SUBPLAN-0005.md`: master cross-repo execution tracker

## Assumptions and Defaults

- Python 3.12+ with `uv` toolchain.
- ECS/Fargate + ALB is canonical runtime platform.
- Same-origin sidecar routing is default browser integration model.
- Runtime stays in monorepo scope, infra stays in `container-craft`.

## Quality Gates

Required for each implementation slice:

- `source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .`
- `source .venv/bin/activate && uv run mypy`
- `source .venv/bin/activate && uv run pytest -q`
- `source .venv/bin/activate && uv run pytest -q`
  `packages/nova_file_api/tests/test_generated_client_smoke.py`

## Progress Log

- 2026-02-12: Implemented runtime API foundation and operational endpoints.
- 2026-02-12: Implemented auth modes with threadpool boundary for local JWT
  verification.
- 2026-02-12: Implemented two-tier cache, async job endpoints, EMF helper, and
  activity rollup backends.
- 2026-02-12: Added idempotency replay handling for `uploads/initiate` and
  `jobs/enqueue`.
- 2026-02-12: Added health + idempotency test coverage and verified gates.
- 2026-02-12: Updated plan/ADR/SPEC/subplan docs for locked production
  architecture and cross-repo execution.
- 2026-02-12: Migrated ADR/SPEC requirement links to current requirement IDs
  and removed legacy traceability alias anchors.
- 2026-02-12: Fixed queue publish error propagation, readiness semantics, and
  DynamoDB distinct event-type rollups; added tests and fail-fast backend
  configuration checks.
- 2026-02-12: Completed full docs hardening pass across README/PRD/AGENTS,
  requirements, SPECs, ADRs, and subplans using AWS docs + Context7 + Exa
  research inputs.
- 2026-02-12: Added worker result-update endpoint contract docs, enforced async
  job state transition validation (`409 conflict` on invalid transitions), and
  expanded tests for transition correctness.
- 2026-02-12: Added explicit worker observability metrics for queue lag and
  worker update throughput; expanded job-service tests for metric coverage.
- 2026-02-12: Re-ran required quality gates after observability updates
  (`ruff`, `mypy`, `pytest`), all green with 23 passing tests.
- 2026-02-12: Added OpenAPI contract regression, log sanitization, and EMF
  payload tests; extended auth/cache regressions for required scopes,
  permissions, and Redis fallback behavior.
- 2026-02-12: Re-ran runtime quality gates after test expansion:
  `ruff`, `mypy`, `pytest` all green (`45` passing tests).
- 2026-02-12: Re-ran cross-repo gates:
  - `container-craft`: `ruff`, `mypy`, `pytest` all green (`48` passing)
  - `dash-pca`: `ruff`, `pyright`, `pytest` all green
    (`353` passing, `1` skipped)
- 2026-02-12: Validated requirements traceability anchors in docs:
  `60` links checked across `17` markdown files, `0` missing anchors.
- 2026-02-12: Reworked `nova_dash_bridge` transfer runtime to delegate
  control-plane transfer operations to `nova_file_api.TransferService`,
  reducing duplicate transfer orchestration logic.
- 2026-02-12: Added generated-client contract smoke coverage via
  `openapi-python-client` in
  `packages/nova_file_api/tests/test_generated_client_smoke.py`.
- 2026-02-12: Re-ran runtime gates after bridge delegation and contract smoke
  additions: `ruff`, `mypy`, and `pytest` all green (`46` passing tests).
- 2026-02-12: Added queue retry/pressure regression coverage for
  `SqsJobPublisher` and published release closure artifacts:
  release notes, hard-cutover checklist, version manifest, and legacy
  archive/redirect guide.
- 2026-02-12: Re-ran required runtime quality gates:
  `ruff`, `mypy`, and `pytest` all green (`49` passing tests).
- 2026-02-12: Re-verified hard-cutover routes via generated OpenAPI path
  inspection; confirmed no runtime usage of legacy names or routes.
- 2026-02-12: Re-ran generated-client smoke gate:
  `packages/nova_file_api/tests/test_generated_client_smoke.py`
  (`1` passing test).
- 2026-02-12: Added operator runbook for remaining external gates:
  `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`.
- 2026-02-13: Review regression hardening:
  - Before: async uploader polling called `GET /api/jobs/{job_id}` without
    same-origin caller-scope headers, causing `401 missing session scope`.
  - After: browser polling forwards `X-Session-Id` for body-less job status
    polling and includes regression contract coverage.
  - Before: EMF payload was emitted under `emf=\"<json string>\"`, which
    prevented CloudWatch EMF extraction.
  - After: EMF payload fields (`_aws`, metric value, dimensions) emit as
    top-level structured log fields.
  - Added/updated tests:
    `packages/nova_file_api/tests/test_jobs.py`,
    `packages/nova_file_api/tests/test_metrics.py`,
    `packages/nova_file_api/tests/test_dash_bridge_asset_contract.py`.
  - Source references:
    - CloudWatch EMF specification:
      <https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html>
    - Fetch API request options (`headers`, `credentials`):
      <https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch>

## Source References

- FastAPI best practices:
  <https://github.com/zhanymkanov/fastapi-best-practices>
- FastAPI deployment and lifespan:
  <https://fastapi.tiangolo.com/deployment/server-workers/>
  <https://fastapi.tiangolo.com/advanced/events/>
- Starlette threadpool:
  <https://www.starlette.io/threadpool/>
- AnyIO threads:
  <https://anyio.readthedocs.io/en/latest/threads.html>
- AWS ECS health checks:
  <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/load-balancer-healthcheck.html>
- Kubernetes readiness/liveness probes:
  <https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/>
- AWS presigned URL guardrails:
  <https://docs.aws.amazon.com/prescriptive-guidance/latest/presigned-url-best-practices/introduction.html>
- AWS SQS request error handling:
  <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/handling-request-errors.html>
- AWS SQS error handling patterns:
  <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/best-practices-error-handling.html>
- AWS SQS SendMessage API:
  <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_SendMessage.html>
- AWS SQS available CloudWatch metrics:
  <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-available-cloudwatch-metrics.html>
- AWS SDK retry behavior:
  <https://docs.aws.amazon.com/general/latest/gr/api-retries.html>
- CloudWatch EMF:
  <https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html>
- CloudWatch cardinality:
  <https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Application-Signals-Cardinality.html>
- DynamoDB best practices:
  <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html>
- DynamoDB UpdateItem:
  <https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_UpdateItem.html>
- DynamoDB condition expressions:
  <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html>
- DynamoDB atomic counter examples:
  <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/example_dynamodb_Scenario_AtomicCounterOperations_section.html>
- ElastiCache best practices:
  <https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/BestPractices.html>
