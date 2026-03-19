# Final Plan (Superseded Notice)

> Supersession Notice (2026-02-28)
>
> This document is retained for historical context and is non-authoritative where it conflicts with the finalized consolidation architecture.
>
> Canonical authority:
>
> - docs/architecture/adr/superseded/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md
> - docs/architecture/adr/superseded/ADR-0014-container-craft-capability-absorption-and-repo-retirement.md
> - docs/architecture/adr/ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md
> - docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md
> - docs/architecture/spec/superseded/SPEC-0011-multi-language-sdk-architecture-and-package-map.md
> - docs/architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md
> - docs/architecture/spec/superseded/SPEC-0013-container-craft-capability-absorption-execution-spec.md
> - docs/architecture/spec/superseded/SPEC-0014-container-craft-capability-inventory-and-absorption-map.md
> - docs/architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md
> - docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md
>
> Status: Reference-only for superseded sections.

## Migration Addendum (2026-03-03)

- This file remains historical execution evidence and is non-authoritative for
  active route contract behavior.
- Active route authority is hard-cut canonical `/v1/*` + `/metrics/summary`
  (`ADR-0023`, `SPEC-0000`, `SPEC-0016`).
- Supersession status: baseline and capability authority in this file is now
  replaced by active updates in `SPEC-0000`, `SPEC-0003`, `SPEC-0004`,
  `SPEC-0008`, and `SPEC-0015`.
- Route namespace supersession: `/api/*`, `/healthz`, and `/readyz` are
  removed from active runtime contract.

## Final Hard-Cutover Monorepo Plan: nova Runtime + container-craft Infra

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

- packages/nova_auth_api/
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
- [x] Add package-owned `nova_file_api.main:app` entrypoint importing `nova_file_api`.
- [x] Add package-owned `nova_auth_api.main:app` entrypoint from the current auth spec.
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
  `docs/runbooks/release/nonprod-live-validation-runbook.md`.
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

- [x] Update `docs/architecture/requirements.md` for new endpoint paths and package names.
- [x] Update `README.md` to reflect new API paths, package names, and cutover guidance.
- [x] Rewrite `docs/plan/PLAN.md` to final monorepo architecture state.
- [x] Rewrite `docs/history/2026-03-v1-hard-cut/subplans/SUBPLAN-0001..N.md` to new execution order.
- [x] Rewrite `docs/history/2026-03-v1-hard-cut/triggers/TRIGGER-0001..N.md` to new names/paths/tools.
- [x] Update affected ADRs in `docs/architecture/adr/` and SPECs in
  `docs/architecture/spec/` for any route/package contract change.
- [x] Validate `docs/architecture/traceability.md` links and requirement anchors
  against the updated `docs/architecture/requirements.md`.
- [x] Remove any stale references to deprecated route/package names.
- [x] Ensure PR description and `docs/plan/PLAN.md` reference public-contract
  docs updates when routes/packages change.

### PR-0009: Release gates + documentation closure

- [x] Run quality gates in monorepo and affected external repos.
- [ ] Validate cross-repo E2E path: browser upload -> enqueue -> worker update -> result/download.
- [ ] Owner + target date recorded for cross-repo E2E validation.
- [ ] Sign-off recorded for cross-repo E2E validation via
  `docs/runbooks/release/nonprod-live-validation-runbook.md`.
- [ ] Validate dashboards/alarms and synthetic failure scenarios.
- [ ] Owner + target date recorded for dashboard/alarm validation.
- [ ] Sign-off recorded for dashboard/alarm validation via
  `docs/runbooks/release/nonprod-live-validation-runbook.md`.
- [x] Finalize active documentation cleanup for post-cutover steady state.
- [x] Publish modular CI/CD provisioning and secrets guide set in `nova` and
  mirrored operator guide set in `container-craft` with action-first and CLI
  fallback instructions.
- [x] Add day-0 operator checklists in both repos and complete docs integrity
  pass (link target + required sections).
- [x] Add one-shot operator command pack script for faster day-0 execution:
  `scripts/release/day-0-operator-command-pack.sh`.
- [x] Publish release notes with hard-cutover migration checklist.
- [x] Publish operator runbook for live AWS validation gates:
  `docs/runbooks/release/nonprod-live-validation-runbook.md`.

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
     (tracked via `docs/runbooks/release/nonprod-live-validation-runbook.md`).
   - [ ] Owner + target date recorded for non-prod smoke.
   - [ ] Sign-off recorded for non-prod smoke via
     `docs/runbooks/release/nonprod-live-validation-runbook.md`.

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

- `docs/runbooks/release/nonprod-live-validation-runbook.md`

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
  `docs/runbooks/release/nonprod-live-validation-runbook.md`.
- 2026-02-13: Implemented cache/idempotency addendum:
  async cache call-path completion across auth/API/idempotency, explicit
  idempotency claim/commit/discard lifecycle for mutation safety, redis env
  contract normalization to `CACHE_REDIS_*` and `CACHE_KEY_*`, and async
  readiness shared-cache ping wiring.
- 2026-02-23: Review remediation hardening:
  - Before: request-model validation errors returned FastAPI default
    `422 {"detail": ...}` in `nova_file_api` and `nova_auth_api`.
  - After: both services return canonical `ErrorEnvelope` for
    `RequestValidationError` with `error.code/message/details/request_id`.
  - Before: `nova_dash_bridge.download_object_bytes` could raise on oversize
    checks without closing S3 `StreamingBody`.
  - After: all download paths (including early exits) close the stream.
  - Added/updated tests:
    `packages/nova_auth_api/tests/test_app.py`,
    `packages/nova_file_api/tests/test_app_health.py`,
    `packages/nova_file_api/tests/test_dash_bridge_download.py`.
  - Source references:
    - FastAPI error handling:
      <https://fastapi.tiangolo.com/tutorial/handling-errors/>
    - Boto3 `get_object`:
      <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/get_object.html>
    - Botocore `StreamingBody` reference:
      <https://docs.aws.amazon.com/botocore/latest/reference/response.html>
- 2026-02-23: Same-origin/job/error regression remediation:
  - Before: same-origin scope could resolve from `X-Scope-Id` before
    `X-Session-Id`; body/header scope conflicts were not rejected.
  - After: same-origin precedence is `X-Session-Id` -> body `session_id` ->
    `X-Scope-Id`, and conflicting header/body session scope now fails with
    `401` (`conflicting session scope`).
  - Before: `FileTransferError` did not initialize base `Exception`, causing
    empty `str(exc)`/`exc.args` in diagnostics.
  - After: `FileTransferError` and `JobPublishError` initialize base exception
    messages.
  - Before: in-memory enqueue always auto-completed.
  - After: `MemoryJobPublisher(process_immediately=False)` preserves
    `pending` state.
  - Added/updated tests:
    `packages/nova_file_api/tests/test_auth.py`,
    `packages/nova_file_api/tests/test_jobs.py`.
  - Source references:
    - FastAPI header parameters:
      <https://fastapi.tiangolo.com/tutorial/header-params/>
    - Python dataclasses:
      <https://docs.python.org/3/library/dataclasses.html>
- 2026-02-23: Packaging/job/readiness regression remediation:
  - Before: workspace package/app `pyproject.toml` files used
    `readme = "../../README.md"`, which fails isolated package builds.
  - After: all affected app/package manifests now use in-project
    `readme = "README.md"` with local README files.
  - Before: succeeded worker updates could retain non-null `error` when result
    payloads were provided.
  - After: succeeded updates always normalize `error` to `null`, preserving
    provided result payloads.
  - Before: placeholder `FILE_TRANSFER_BUCKET` default could produce
    false-positive readiness.
  - After: default bucket is blank and `/readyz` treats blank/whitespace bucket
    values as unconfigured.
  - Added/updated tests:
    `packages/nova_file_api/tests/test_jobs.py`,
    `packages/nova_file_api/tests/test_app_health.py`.
  - Source references:
    - PEP 621 `readme` metadata:
      <https://peps.python.org/pep-0621/>
    - Hatch metadata/readme configuration:
      <https://github.com/pypa/hatch/blob/master/docs/config/metadata.md>
    - pydantic-settings BaseSettings behavior:
      <https://github.com/pydantic/pydantic-settings/blob/main/docs/index.md>
- 2026-02-24: CI/CD release deploy spec implementation update:
  - Added selective release tooling under `scripts/release/` with tests:
    changed-unit detection, deterministic bumping, version apply, and manifest
    rendering.
  - Added GitHub workflow layer:
    `ci.yml`, `release-plan.yml`, `release-apply.yml`,
    `verify-signature.yml`.
  - Added release/deploy buildspecs and service Dockerfiles:
    `buildspec-release.yml` now publishes changed packages to CodeArtifact and
    pushes immutable ECR image digests; `buildspec-deploy-validate.yml` gates
    `/healthz`, `/readyz`, and `/metrics/summary`.
  - Added `container-craft` Nova CI/CD stacks:
    `infra/nova/nova-iam-roles.yml`,
    `infra/nova/nova-codebuild-release.yml`,
    `infra/nova/nova-ci-cd.yml`,
    including template trigger wiring and CodeArtifact package-group hardening.
  - Synchronized execution tracking in
    `.agents/plans/2026-02-23-nova-aws-cicd-release-deploy-spec.md`.
  - Remaining external gates (manual/non-local):
    Secrets Manager signing secret provisioning, CodeConnections activation, and
    first Dev->Prod promotion evidence capture in
    `docs/runbooks/release/nonprod-live-validation-runbook.md`.
- 2026-02-24: Release automation correctness remediation:
  - `buildspec-release.yml` now resolves changed publish units from signed
    release commit diff (`HEAD^..HEAD`) and publishes unit paths from
    `changed-units.json`.
  - `buildspec-release.yml` twine uploads now explicitly target CodeArtifact via
    `--repository codeartifact`.
  - `release-apply.yml` now gates execution to `main` branch paths only:
    `workflow_run` requires `head_branch == main`; `workflow_dispatch` requires
    `refs/heads/main`.
  - `release-apply.yml` checkout is pinned to
    `github.event.workflow_run.head_sha` for `workflow_run` invocations.
  - Release docs synchronized:
    `README.md`,
    `docs/architecture/spec/SPEC-0004-ci-cd-and-docs.md`,
    `docs/runbooks/release/release-policy.md`,
    `docs/runbooks/release/release-runbook.md`.
