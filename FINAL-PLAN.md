# Final Hard-Cutover Monorepo Plan: nova Runtime + container-craft Infra

## Summary

This plan is decision-complete and aligned to your locked choices:

- Runtime monorepo scope only (not moving full dash-pca into monorepo).
- Hard cutover (no compatibility shims).
- In-place restructure of current repo.
- Repo/package rename now:
  - Repo identity: nova
  - Python packages: nova_file_api, nova_auth_api, nova_dash_bridge
- API hard cutover to functional split paths.
- dash-pca migration is mandatory in the same release gate.
- Old runtime repos are archived and redirected after cutover.

  Audit result from current diffs/logs:

- No evidence of losing critical runtime semantics (auth/idempotency/async/metrics).
- Confirmed divergence is primarily topology/naming/path contract completeness.
- This plan closes that gap.

## Locked Decisions and Scores

Scoring model:

- Solution leverage 35%
- Application value 30%
- Maintenance/cognitive load 25%
- Architectural adaptability 10%

| Decision | Score |
| --- | --- |
| Runtime-only monorepo + separate infra repo | 9.6/10 |
| In-place monorepo restructure in current repo | 9.3/10 |
| Hard cutover with no shims | 9.1/10 |
| Repo/package rename now | 9.2/10 |
| Functional path split (/api/transfers/*, /api/jobs/*) | 9.4/10 |
| Same-window mandatory dash-pca cutover gate | 9.3/10 |

## Public API / Interface Changes (Final)

### HTTP endpoint cutover

Remove old `/api/file-transfer/*` routes and replace with:

- POST /api/transfers/uploads/initiate
- POST /api/transfers/uploads/sign-parts
- POST /api/transfers/uploads/complete
- POST /api/transfers/uploads/abort
- POST /api/transfers/downloads/presign
- POST /api/jobs/enqueue
- GET /api/jobs/{job_id}
- POST /api/jobs/{job_id}/cancel
- POST /api/jobs/{job_id}/result
- GET /healthz
- GET /readyz
- GET /metrics/summary

### Python package cutover

- Replace deprecated transfer-api imports with nova_file_api.
- Use nova_dash_bridge as the canonical bridge import namespace.
- Remote auth service package becomes nova_auth_api.

### Contract invariants retained

- Error envelope stays error.code/message/details/request_id.
- 503 queue_unavailable on enqueue publish failure.
- Failed enqueue is not idempotency replay cached.
- Worker result transition rules and 409 conflict.
- JWT local verification stays behind thread boundary.
- No presigned URL/token/signature logging.

## Target Monorepo Layout (In-Place)

Create this structure in current repo:

- apps/nova_file_api_service/
- apps/nova_auth_api_service/
- packages/nova_file_api/
- packages/nova_dash_bridge/
- packages/contracts/ (OpenAPI artifacts + schema utilities only)
- docs/architecture/
- docs/plan/

  Root standardization:

- Root pyproject.toml becomes workspace coordinator.
- Package-level pyproject.toml files per app/package.
- Shared lint/type/test policy at root (ruff, mypy, pytest).
- Max line length 80 and Ruff D docstring rules enforced in source modules.

## Execution Plan (PR-Sized, No Open Decisions Left)

### PR-0001: Monorepo scaffold + namespace rename baseline

- [x] Add workspace layout directories listed above.
- [x] Move existing runtime source into packages/nova_file_api/src/nova_file_api.
- [x] Move existing bridge source plan into packages/nova_dash_bridge.
- [x] Add apps/nova_file_api_service app entrypoint importing nova_file_api.
- [x] Add apps/nova_auth_api_service service skeleton from current auth spec.
- [x] Update root/package metadata names to nova,
  nova_file_api, nova_auth_api, nova_dash_bridge.
- [x] Update import paths across code/tests to new namespaces.
- [x] Keep behavior unchanged in this PR (rename/layout only).

### PR-0002: HTTP path hard cutover to functional split

- [x] Refactor routers from legacy `/api/file-transfer/*` to `/api/transfers/*`
  and `/api/jobs/*`.
- [x] Update route constants, OpenAPI tags, operation IDs, and examples.
- [x] Remove old route mounts (no dual routing).
- [x] Update all tests to new paths.
- [x] Update worker callback docs and token header docs under new
  /api/jobs/*.

### PR-0003: Auth/JWT hardening confirmation under renamed packages

- [x] Keep local verifier as canonical default via oidc-jwt-verifier.
- [x] Catch `oidc-jwt-verifier` `AuthError` in JWT verification flow and map
  to HTTP 401/403 via `err.status_code`, including
  `WWW-Authenticate: err.www_authenticate_header()`.
- [x] Configure AnyIO thread limiter during lifespan init using
  `OIDC_VERIFIER_THREAD_TOKENS`; if unset, document/default to AnyIO's
  40-token thread pool behavior for `anyio.to_thread.run_sync`.
- [x] Keep remote auth optional and fail-closed.
- [x] Add/refresh tests for invalid issuer/audience/exp/scope mapping.

### PR-0004: Async jobs, idempotency, cache, observability lock-in

- [x] Preserve 503 queue_unavailable contract and failed job persistence.
- [x] Keep enqueue failure out of idempotency success replay cache.
- [x] Preserve legal status transitions and idempotent terminal same-state
  updates.
- [x] Keep queue lag and worker throughput metrics.
- [x] Add missing explicit tests:
- [x] Redis outage fallback behavior.
- [x] Remote auth fail-closed behavior.
- [x] Cache metric coverage (hit/miss/fallback counters).

### PR-0005: container-craft hard alignment for new path contract

  Repo: ~/repos/work/infra-stack/container-craft

- [x] Update ALB routing rules for async jobs from `/api/transfers/*` to
  `/api/jobs/*`.
- [x] Keep explicit ALB routing for transfer endpoints on `/api/transfers/*`.
- [ ] Keep health check route alignment and tuned intervals/thresholds.
- [x] Health check alignment owner assigned:
  container-craft platform owner (`@infra-platform`) with target date
  `2026-02-20` before prod cutover.
- [ ] Health check alignment sign-off completed via
  `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`.
- [x] Keep/add env mappings for SQS/Redis/DynamoDB backends.
- [x] Validate retry env contract:
- [x] `JOBS_SQS_RETRY_MODE`
- [x] `JOBS_SQS_RETRY_TOTAL_MAX_ATTEMPTS`
- [x] Validate least-privilege IAM for S3/KMS/SQS/DynamoDB/Redis.

### PR-0006: nova_dash_bridge bridge package finalization

Repo: `monorepo packages/nova_dash_bridge` and external source parity as needed

- [x] Finalize bridge API to call new `/api/transfers/*` + `/api/jobs/*`.
- [x] Keep async uploader behaviors and polling contract.
- [x] Update assets and integration tests for new paths.
- [x] Remove residual runtime logic that belongs in nova_file_api.

### PR-0007: dash-pca mandatory same-window migration

Repo: `~/repos/work/pca-analysis-dash/dash-pca`

- [x] Replace old package imports with nova_dash_bridge and nova_file_api.
- [x] Update endpoint calls to `/api/transfers/*` and `/api/jobs/*`.
- [x] Keep PCA policy (200 MB, .csv/.xlsx) enforced.
- [x] Validate sync and async flows with new contracts.
- [x] Update tests and app settings docs.
- [x] This PR is required before release approval.

### PR-0008: ADR/SPEC/PLAN/traceability full rewrite to final IDs and links

In monorepo docs:

- [x] Rewrite `docs/plan/PLAN.md` to final monorepo architecture state.
- [x] Rewrite `docs/plan/subplans/SUBPLAN-0001..N.md` to new execution order.
- [x] Rewrite `docs/plan/triggers/TRIGGER-0001..N.md` to new names/paths/tools.
- [x] Update all ADRs/SPECs to new endpoint paths and package names.
- [x] Validate every traceability link targets current requirement anchors.
- [x] Remove any stale references to deprecated route/package names.

### PR-0009: Release gates + documentation closure

- [x] Run quality gates in monorepo and affected external repos.
- [ ] Validate cross-repo E2E path: browser upload -> enqueue -> worker update -> result/download.
- [ ] Owner + target date recorded for cross-repo E2E validation.
- [ ] Sign-off recorded for cross-repo E2E validation via
  `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`.
- [ ] Validate dashboards/alarms and synthetic failure scenarios.
- [ ] Owner + target date recorded for dashboard/alarm validation.
- [ ] Sign-off recorded for dashboard/alarm validation via
  `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`.
- [x] Finalize active documentation cleanup for post-cutover steady state.
- [x] Publish release notes with hard-cutover migration checklist.
- [x] Publish operator runbook for live AWS validation gates:
  `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`.

## Testing and Acceptance Scenarios

1. Contract and routing

   - [x] OpenAPI contains only new `/api/transfers/*` and `/api/jobs/*` paths.
   - [x] No deprecated alias route namespace remains.
   - [x] Generated client smoke tests pass.

2. Security/auth

   - [x] JWT invalid issuer/audience/exp/nbf rejected correctly.
   - [x] Required scopes/permissions enforced.
   - [x] Remote auth fail-closed behavior verified.
   - [x] Logs contain no token/presigned URL/query signature leakage.

3. Async reliability

   - [x] Enqueue success path persists and completes.
   - [x] Queue publish failure returns 503 queue_unavailable.
   - [x] Failed enqueue is not replayed as success via idempotency.
   - [x] Invalid worker transition returns 409 conflict.
   - [x] Same-origin browser polling propagates caller scope on body-less
     `GET /api/jobs/{job_id}` requests via `X-Session-Id`.

4. Cache and resilience

   - [x] Local cache hit/miss behavior verified.
   - [x] Redis outage degrades to local-only mode safely.
   - [x] Recovery path repopulates shared cache correctly.

5. Observability/operations

   - [x] EMF payloads valid and within dimension limits.
   - [x] EMF fields are emitted as top-level structured log fields (including
     `_aws`), not nested JSON strings.
   - [x] `/readyz` excludes feature-flag state from pass/fail logic.

6. Cross-repo integration

   - [x] `container-craft` routes and env mappings align with new API.
   - [x] dash-pca updated and passing against new contracts.
   - [ ] End-to-end non-prod smoke succeeds before prod release
     (tracked via `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`).
   - [ ] Owner + target date recorded for non-prod smoke.
   - [ ] Sign-off recorded for non-prod smoke via
     `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`.

## Assumptions and Defaults

- Python 3.12+ and uv workspace flow.
- ECS/Fargate + ALB sidecar remains canonical runtime deployment.
- Infra remains separate in `container-craft`.
- Hard cutover means no compatibility alias routes and no namespace shims.
- dash-pca migration is release-blocking.

## Remaining External Gates

The following gates require live non-prod AWS access:

- Sidecar ALB route + health-check verification.
- Cross-repo non-prod E2E smoke.
- CloudWatch dashboard/alarm synthetic-failure validation.

Execution and evidence checklist:

- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`

## Primary Sources to Use During Execution

- FastAPI lifespan/events: <https://fastapi.tiangolo.com/advanced/events/>
- FastAPI workers: <https://fastapi.tiangolo.com/deployment/server-workers/>
- FastAPI security: <https://fastapi.tiangolo.com/tutorial/security/>
- Starlette threadpool: <https://www.starlette.io/threadpool/>
- AnyIO thread guidance: <https://anyio.readthedocs.io/en/latest/threads.html>
- OpenAPI spec: <https://spec.openapis.org/oas/latest.html>
- RFC6750 bearer: <https://datatracker.ietf.org/doc/html/rfc6750>
- ECS health checks: <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/load-balancer-healthcheck.html>
- SQS error handling: <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/handling-request-errors.html>
- SQS metrics: <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-available-cloudwatch-metrics.html>
- SQS SendMessage API: <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_SendMessage.html>
- CloudWatch EMF spec: <https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html>
- CloudWatch cardinality: <https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Application-Signals-Cardinality.html>
- DynamoDB condition expressions: <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html>
- DynamoDB UpdateItem API: <https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_UpdateItem.html>
- Presigned URL guardrails: <https://docs.aws.amazon.com/prescriptive-guidance/latest/presigned-url-best-practices/introduction.html>
- FastAPI best-practices repo: <https://github.com/zhanymkanov/fastapi-best-practices>
- FastAPI best-practices AGENTS: <https://raw.githubusercontent.com/zhanymkanov/fastapi-best-practices/master/AGENTS.md>

## Execution Log

- 2026-02-12: Created monorepo runtime layout:
  `apps/nova_file_api_service`, `apps/nova_auth_api_service`,
  `packages/nova_file_api`, `packages/nova_auth_api`,
  `packages/nova_dash_bridge`, `packages/contracts`.
- 2026-02-12: Migrated runtime source to
  `packages/nova_file_api/src/nova_file_api` and tests to
  `packages/nova_file_api/tests`.
- 2026-02-12: Added workspace/package metadata:
  root `pyproject.toml` renamed to `nova`; package-level
  `pyproject.toml` files added for `nova_file_api`, `nova_auth_api`,
  `nova_dash_bridge`, and service wrappers.
- 2026-02-12: Implemented auth service skeleton package:
  `packages/nova_auth_api` with `/healthz`, `/v1/token/verify`,
  `/v1/token/introspect`, canonical error envelope, and tests.
- 2026-02-12: Completed API route hard cutover in `nova_file_api`:
  transfer endpoints on `/api/transfers/*`, async jobs on `/api/jobs/*`,
  ops endpoint on `/metrics/summary`.
- 2026-02-12: Completed bridge cutover in `nova_dash_bridge`:
  Python imports renamed, asset prefix renamed, JS uploader now uses
  `transfersEndpointBase` and `jobsEndpointBase` defaults.
- 2026-02-12: Started docs/spec route normalization from legacy
  `/api/transfers/*` to split routes; traceability cleanup in progress.
- 2026-02-12: Passed required quality gates from monorepo root:
  - `source .venv/bin/activate && uv run ruff check . --fix`
  - `source .venv/bin/activate && uv run ruff format .`
  - `source .venv/bin/activate && uv run mypy`
  - `source .venv/bin/activate && uv run pytest -q`
  - Current local result: `26 passed`.
- 2026-02-12: Expanded runtime regression coverage:
  - OpenAPI split-route contract tests
  - auth scope/permission enforcement and RFC6750 mapping tests
  - cache fallback and cache metric counter tests
  - logging sanitization and EMF payload tests
- 2026-02-12: Re-ran required quality gates from monorepo root:
  - `source .venv/bin/activate && uv run ruff check . --fix`
  - `source .venv/bin/activate && uv run ruff format .`
  - `source .venv/bin/activate && uv run mypy`
  - `source .venv/bin/activate && uv run pytest -q`
  - Current local result: `45 passed`.
- 2026-02-12: Re-ran external repo gates:
  - `container-craft`: `uv run -- ruff check .`, `uv run -- mypy`,
    `uv run -- pytest -q` (`48 passed`)
  - `dash-pca`: `ruff`, `pyright`, and `pytest -q`
    (`353 passed, 1 skipped`)
- 2026-02-12: Validated requirements traceability anchors:
  - checked `60` links across `17` docs files
  - missing anchors: `0`
- 2026-02-12: Refactored `nova_dash_bridge.FileTransferService` to delegate
  control-plane transfer operations to `nova_file_api.TransferService`,
  preserving bridge-only policy and export/download helpers.
- 2026-02-12: Added generated OpenAPI client smoke test:
  `packages/nova_file_api/tests/test_generated_client_smoke.py`
  using `openapi-python-client` generation + compile verification.
- 2026-02-12: Re-ran runtime quality gates after bridge delegation + client
  smoke implementation:
  - `source .venv/bin/activate && uv run ruff check . --fix`
  - `source .venv/bin/activate && uv run ruff format .`
  - `source .venv/bin/activate && uv run mypy`
  - `source .venv/bin/activate && uv run pytest -q`
  - Current local result: `46 passed`.
- 2026-02-12: Added queue retry/pressure test coverage for `SqsJobPublisher`
  configuration and publish-failure mappings.
- 2026-02-12: Published release closure artifacts:
  - `docs/plan/release/RELEASE-NOTES-2026-02-12.md`
  - `docs/plan/release/HARD-CUTOVER-CHECKLIST.md`
  - `docs/plan/release/RELEASE-VERSION-MANIFEST.md`
- 2026-02-12: Re-ran required runtime quality gates:
  - `source .venv/bin/activate && uv run ruff check . --fix`
  - `source .venv/bin/activate && uv run ruff format .`
  - `source .venv/bin/activate && uv run mypy`
  - `source .venv/bin/activate && uv run pytest -q`
  - Current local result: `49 passed`.
- 2026-02-12: Re-verified hard-cutover runtime contract exposure:
  - OpenAPI paths include only `/api/transfers/*`, `/api/jobs/*`,
    `/healthz`, `/readyz`, and `/metrics/summary`.
  - Runtime source contains no legacy import/path usage
    (deprecated alias routes and retired package/module names).
- 2026-02-12: Re-ran generated-client smoke gate:
  - `source .venv/bin/activate && uv run pytest -q`
    `packages/nova_file_api/tests/test_generated_client_smoke.py`
  - Result: `1 passed`.
- 2026-02-12: Added operator runbook for remaining external live gates:
  `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`.
- 2026-02-13: Implemented cache/idempotency addendum:
  async cache call-path completion across auth/API/idempotency, explicit
  idempotency claim/commit/discard lifecycle for mutation safety, redis env
  contract normalization to `CACHE_REDIS_*` and `CACHE_KEY_*`, and async
  readiness shared-cache ping wiring.
