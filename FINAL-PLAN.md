# Final Hard-Cutover Monorepo Plan: aws-file-platform Runtime + container-craft Infra

## Summary

This plan is decision-complete and aligned to your locked choices:

- Runtime monorepo scope only (not moving full dash-pca into monorepo).
- Hard cutover (no compatibility shims).
- In-place restructure of current repo.
- Repo/package rename now:
  - Repo identity: aws-file-platform
  - Python packages: aws_file_api, aws_auth_api, aws_dash_bridge
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
- POST /api/jobs/{job_id}/result (worker/internal)
- GET /healthz
- GET /readyz
- GET /metrics/summary

### Python package cutover

- Replace aws_file_transfer_api imports with aws_file_api.
- Replace aws_dash_s3_file_handler imports with aws_dash_bridge.
- Remote auth service package becomes aws_auth_api.

### Contract invariants retained

- Error envelope stays error.code/message/details/request_id.
- 503 queue_unavailable on enqueue publish failure.
- Failed enqueue is not idempotency replay cached.
- Worker result transition rules and 409 conflict.
- JWT local verification stays behind thread boundary.
- No presigned URL/token/signature logging.

## Target Monorepo Layout (In-Place)

Create this structure in current repo:

- apps/aws_file_api_service/
- apps/aws_auth_api_service/
- packages/aws_file_api/
- packages/aws_dash_bridge/
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
- [x] Move existing runtime source into packages/aws_file_api/src/aws_file_api.
- [x] Move existing bridge source plan into packages/aws_dash_bridge.
- [x] Add apps/aws_file_api_service app entrypoint importing aws_file_api.
- [x] Add apps/aws_auth_api_service service skeleton from current auth spec.
- [x] Update root/package metadata names to aws-file-platform,
  aws_file_api, aws_auth_api, aws_dash_bridge.
- [x] Update import paths across code/tests to new namespaces.
- [ ] Keep behavior unchanged in this PR (rename/layout only).

### PR-0002: HTTP path hard cutover to functional split

- [x] Refactor routers from `/api/file-transfer/*` to `/api/transfers/*`
  and /api/jobs/*.
- [x] Update route constants, OpenAPI tags, operation IDs, and examples.
- [x] Remove old route mounts (no dual routing).
- [x] Update all tests to new paths.
- [x] Update worker callback docs and token header docs under new
  /api/jobs/*.

### PR-0003: Auth/JWT hardening confirmation under renamed packages

- [ ] Keep local verifier as canonical default via oidc-jwt-verifier.
- [ ] Verify all sync JWT verification calls remain on thread boundary.
- [ ] Keep remote auth optional and fail-closed.
- [ ] Ensure RFC6750 WWW-Authenticate behavior remains consistent.
- [ ] Add/refresh tests for invalid issuer/audience/exp/scope mapping.

### PR-0004: Async jobs, idempotency, cache, observability lock-in

- [ ] Preserve 503 queue_unavailable contract and failed job persistence.
- [ ] Keep enqueue failure out of idempotency success replay cache.
- [ ] Preserve legal status transitions and idempotent terminal same-state updates.
- [ ] Keep queue lag and worker throughput metrics.
- [ ] Add missing explicit tests:
- [ ] Redis outage fallback behavior.
- [ ] Remote auth fail-closed behavior.
- [ ] Cache metric coverage (hit/miss/fallback counters).

### PR-0005: container-craft hard alignment for new path contract

  Repo: ~/repos/work/infra-stack/container-craft

- [ ] Update ALB routing rules from `/api/file-transfer/*` to:
- [ ] `/api/transfers/*`
- [ ] `/api/jobs/*`
- [ ] Keep health check route alignment and tuned intervals/thresholds.
- [ ] Keep/add env mappings for SQS/Redis/DynamoDB backends.
- [ ] Validate retry env contract:
- [ ] `JOBS_SQS_RETRY_MODE`
- [ ] `JOBS_SQS_RETRY_TOTAL_MAX_ATTEMPTS`
- [ ] Validate least-privilege IAM for S3/KMS/SQS/DynamoDB/Redis.

### PR-0006: aws_dash_bridge bridge package finalization

Repo: `monorepo packages/aws_dash_bridge` and external source parity as needed

- [x] Finalize bridge API to call new `/api/transfers/*` + `/api/jobs/*`.
- [x] Keep async uploader behaviors and polling contract.
- [x] Update assets and integration tests for new paths.
- [ ] Remove residual runtime logic that belongs in aws_file_api.

### PR-0007: dash-pca mandatory same-window migration

Repo: `~/repos/work/pca-analysis-dash/dash-pca`

- [ ] Replace old package imports with aws_dash_bridge and aws_file_api.
- [ ] Update endpoint calls to `/api/transfers/*` and `/api/jobs/*`.
- [ ] Keep PCA policy (200 MB, .csv/.xlsx) enforced.
- [ ] Validate sync and async flows with new contracts.
- [ ] Update tests and app settings docs.
- [ ] This PR is required before release approval.

### PR-0008: ADR/SPEC/PLAN/traceability full rewrite to final IDs and links

In monorepo docs:

- [x] Rewrite `docs/plan/PLAN.md` to final monorepo architecture state.
- [ ] Rewrite `docs/plan/subplans/SUBPLAN-0001..N.md` to new execution order.
- [ ] Rewrite `docs/plan/triggers/TRIGGER-0001..N.md` to new names/paths/tools.
- [x] Update all ADRs/SPECs to new endpoint paths and package names.
- [ ] Validate every traceability link targets current requirement anchors.
- [x] Remove any stale references to deprecated route/package names.

### PR-0009: Release gates + old repo archive/redirect

- [ ] Run quality gates in monorepo and affected external repos.
- [ ] Validate cross-repo E2E path: browser upload -> enqueue -> worker update -> result/download.
- [ ] Validate dashboards/alarms and synthetic failure scenarios.
- [ ] Archive old runtime repos as read-only with migration README redirect.
- [ ] Publish release notes with hard-cutover migration checklist.

## Testing and Acceptance Scenarios

1. Contract and routing

   - [ ] OpenAPI contains only new `/api/transfers/*` and `/api/jobs/*` paths.
   - [ ] No legacy `/api/file-transfer/*` path remains.
   - [ ] Generated client smoke tests pass.

2. Security/auth

   - [ ] JWT invalid issuer/audience/exp/nbf rejected correctly.
   - [ ] Required scopes/permissions enforced.
   - [ ] Remote auth fail-closed behavior verified.
   - [ ] Logs contain no token/presigned URL/query signature leakage.

3. Async reliability

   - [ ] Enqueue success path persists and completes.
   - [ ] Queue publish failure returns 503 queue_unavailable.
   - [ ] Failed enqueue is not replayed as success via idempotency.
   - [ ] Invalid worker transition returns 409 conflict.

4. Cache and resilience

   - [ ] Local cache hit/miss behavior verified.
   - [ ] Redis outage degrades to local-only mode safely.
   - [ ] Recovery path repopulates shared cache correctly.

5. Observability/operations

   - [ ] EMF payloads valid and within dimension limits.
   - [ ] `/readyz` excludes feature-flag state from pass/fail logic.

6. Cross-repo integration

   - [ ] `container-craft` routes and env mappings align with new API.
   - [ ] dash-pca updated and passing against new contracts.
   - [ ] End-to-end non-prod smoke succeeds before prod release.

## Assumptions and Defaults

- Python 3.12+ and uv workspace flow.
- ECS/Fargate + ALB sidecar remains canonical runtime deployment.
- Infra remains separate in `container-craft`.
- Hard cutover means no compatibility alias routes and no namespace shims.
- dash-pca migration is release-blocking.
- Archive old repos after successful production verification.

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
  `apps/aws_file_api_service`, `apps/aws_auth_api_service`,
  `packages/aws_file_api`, `packages/aws_auth_api`,
  `packages/aws_dash_bridge`, `packages/contracts`.
- 2026-02-12: Migrated runtime source to
  `packages/aws_file_api/src/aws_file_api` and tests to
  `packages/aws_file_api/tests`.
- 2026-02-12: Added workspace/package metadata:
  root `pyproject.toml` renamed to `aws-file-platform`; package-level
  `pyproject.toml` files added for `aws_file_api`, `aws_auth_api`,
  `aws_dash_bridge`, and service wrappers.
- 2026-02-12: Implemented auth service skeleton package:
  `packages/aws_auth_api` with `/healthz`, `/v1/token/verify`,
  `/v1/token/introspect`, canonical error envelope, and tests.
- 2026-02-12: Completed API route hard cutover in `aws_file_api`:
  transfer endpoints on `/api/transfers/*`, async jobs on `/api/jobs/*`,
  ops endpoint on `/metrics/summary`.
- 2026-02-12: Completed bridge cutover in `aws_dash_bridge`:
  Python imports renamed, asset prefix renamed, JS uploader now uses
  `transfersEndpointBase` and `jobsEndpointBase` defaults.
- 2026-02-12: Started docs/spec route normalization from legacy
  `/api/file-transfer/*` to split routes; traceability cleanup in progress.
- 2026-02-12: Passed required quality gates from monorepo root:
  - `source .venv/bin/activate && uv run ruff check . --fix`
  - `source .venv/bin/activate && uv run ruff format .`
  - `source .venv/bin/activate && uv run mypy`
  - `source .venv/bin/activate && uv run pytest -q`
  - Current local result: `26 passed`.
