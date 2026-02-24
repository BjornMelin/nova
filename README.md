# nova runtime

![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-0.129%2B-009688?logo=fastapi&logoColor=white) ![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1-6BA539?logo=openapiinitiative&logoColor=white) ![AWS S3](https://img.shields.io/badge/AWS-S3-569A31?logo=amazons3&logoColor=white) ![AWS SQS](https://img.shields.io/badge/AWS-SQS-FF9900?logo=amazonaws&logoColor=white) ![Ruff](https://img.shields.io/badge/lint-ruff-D7FF64?logo=ruff&logoColor=111111) ![Mypy](https://img.shields.io/badge/types-mypy-2A6DB2?logo=python&logoColor=white) ![Pytest](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)

FastAPI control-plane service for direct-to-S3 upload/download orchestration.
The API returns presigned metadata and async job state. It never proxies file
bytes.

## Runtime Capabilities

- Transfer endpoints for single-part and multipart uploads.
- Download presign endpoint.
- Bridge package (`nova_dash_bridge`) delegates control-plane transfer
  operations to `nova_file_api` runtime services.
- Async job endpoints:
  - `POST /api/jobs/enqueue`
  - `GET /api/jobs/{job_id}`
  - `POST /api/jobs/{job_id}/cancel`
  - `POST /api/jobs/{job_id}/result` (worker/internal)
  - same-origin polling clients send caller scope on body-less job routes via
    `X-Session-Id`
  - same-origin scope precedence is `X-Session-Id` -> body `session_id` ->
    `X-Scope-Id`
  - scope conflict handling:
    - `X-Session-Id` + body `session_id` mismatch => `422`
    - `X-Scope-Id` + body `session_id` mismatch (no `X-Session-Id`) => `401`
- Auth modes:
  - same-origin
  - local JWT verification (`oidc-jwt-verifier`)
  - optional remote auth mode (fail-closed)
- Two-tier cache:
  - local in-process TTL cache
  - optional shared Redis cache
- Idempotency replay support for:
  - `POST /api/transfers/uploads/initiate`
  - `POST /api/jobs/enqueue`
- Operational endpoints:
  - `GET /healthz`
  - `GET /readyz`
  - `GET /metrics/summary`

## Production Semantics (Implemented)

### Enqueue reliability contract

- Queue publish failures are surfaced to clients.
- `POST /api/jobs/enqueue` returns:
  - `503 Service Unavailable`
  - `error.code = "queue_unavailable"`
- When enqueue publish fails after record creation, the job record is
  transitioned to `failed`.
- Failed enqueue attempts are not idempotency replay cached.
- In-memory queue mode honors `process_immediately`; when disabled, jobs remain
  `pending` after enqueue.

### Worker result-update contract

- `POST /api/jobs/{job_id}/result` is used by trusted worker
  paths to publish state updates.
- Worker updates must follow legal transitions:
  - `pending -> pending|running|succeeded|failed|canceled`
  - `running -> running|succeeded|failed|canceled`
  - terminal states (`succeeded|failed|canceled`) only allow idempotent
    same-state updates.
- Invalid transitions return `409` with `error.code = "conflict"`.
- `succeeded` updates always normalize `error` to `null`.

### Worker observability contract

- First worker transition out of `pending` records queue lag as
  `jobs_queue_lag_ms`.
- Worker result updates increment throughput counters:
  - `jobs_worker_result_updates_total`
  - `jobs_worker_result_updates_<status>`
- EMF logs are emitted as top-level structured fields (`_aws`, metric name,
  dimensions), not nested JSON strings.
- `GET /metrics/summary` exposes queue-lag latency and worker
  update counters for dashboards.

### Readiness contract

- `/readyz` reflects only critical traffic-serving dependencies.
- Feature flags such as `JOBS_ENABLED` do not affect readiness pass/fail.
- `bucket_configured` is true only when `FILE_TRANSFER_BUCKET` is non-empty
  after trimming whitespace.
- Current readiness checks:
  - `bucket_configured`
  - `shared_cache`

### Activity rollup correctness

- DynamoDB rollups track:
  - `events_total`
  - `active_users_today`
  - `distinct_event_types`
- `active_users_today` and `distinct_event_types` are incremented only when
  first-seen marker writes succeed (conditional write pattern).

## Required Configuration Rules

Startup fails fast for invalid backend selections:

- `JOBS_QUEUE_BACKEND=sqs` and `JOBS_ENABLED=true` requires
  `JOBS_SQS_QUEUE_URL`.
- `ACTIVITY_STORE_BACKEND=dynamodb` requires `ACTIVITY_ROLLUPS_TABLE`.
- Missing/blank `FILE_TRANSFER_BUCKET` keeps `/readyz` in a non-ready state.

Primary operational settings:

- `FILE_TRANSFER_BUCKET`
- `AUTH_MODE`
- `JOBS_ENABLED`
- `JOBS_QUEUE_BACKEND`
- `JOBS_REPOSITORY_BACKEND`
- `JOBS_DYNAMODB_TABLE`
- `JOBS_SQS_QUEUE_URL`
- `JOBS_SQS_RETRY_MODE`
- `JOBS_SQS_RETRY_TOTAL_MAX_ATTEMPTS`
- `JOBS_WORKER_UPDATE_TOKEN`
- `ACTIVITY_STORE_BACKEND`
- `ACTIVITY_ROLLUPS_TABLE`
- `CACHE_REDIS_URL`
- `CACHE_LOCAL_TTL_SECONDS`
- `CACHE_LOCAL_MAX_ENTRIES`
- `CACHE_SHARED_TTL_SECONDS`
- `CACHE_KEY_PREFIX`
- `CACHE_KEY_SCHEMA_VERSION`
- `AUTH_JWT_CACHE_MAX_TTL_SECONDS`
- `IDEMPOTENCY_ENABLED`
- `OIDC_VERIFIER_THREAD_TOKENS`
- `FILE_TRANSFER_THREAD_TOKENS`

## API Base Paths

- Transfers: `/api/transfers`
- Jobs: `/api/jobs`

## Local Development

Run in repository root:

```bash
source .venv/bin/activate && uv lock --check
source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .
source .venv/bin/activate && uv run mypy
source .venv/bin/activate && uv run pytest -q
```

For workspace packaging metadata checks, run isolated builds:

```bash
source .venv/bin/activate && \
for p in packages/nova_file_api packages/nova_auth_api \
  packages/nova_dash_bridge apps/nova_file_api_service \
  apps/nova_auth_api_service; do uv build "$p"; done
```

## Threading and Async Workload Notes

- Sync JWT verification and FastAPI transfer adapters use AnyIO thread pools.
- Environment controls:
  - `OIDC_VERIFIER_THREAD_TOKENS` (default: `40`) for local JWT verification and
    auth API verifier work.
  - `FILE_TRANSFER_THREAD_TOKENS` (default: `80`) for synchronous transfer
    and route adapters.
- Raise these values for higher parallel verification/upload fan-out; lower them
  if you need tighter host resource usage after load testing.

## OpenAPI Contract Smoke

Generated-client smoke coverage is enforced with:

```bash
source .venv/bin/activate && \
uv run pytest -q \
  packages/nova_file_api/tests/test_generated_client_smoke.py
```

The smoke test generates a Python client with `openapi-python-client` from the
runtime OpenAPI schema and verifies generated code compiles successfully.

## Release Automation

Hybrid release model:

1. GitHub Actions handles CI and selective release planning/apply:
   - `.github/workflows/ci.yml`
   - `.github/workflows/release-plan.yml`
   - `.github/workflows/release-apply.yml`
   - `.github/workflows/verify-signature.yml`
   - `release-apply.yml` safety controls:
     - `workflow_run` execution is restricted to successful `main` runs.
     - checkout is pinned to the planned `workflow_run.head_sha`.
     - manual `workflow_dispatch` apply runs are restricted to `main`.
2. Release tooling scripts live under `scripts/release/`:
   - changed unit detection
   - deterministic version planning
   - selective version apply
   - release manifest generation
3. AWS promotion is Dev -> ManualApproval -> Prod in `container-craft` CI/CD
   stacks, consuming immutable artifacts from the signed release commit.
4. Release build contract:
   - buildspec: `buildspecs/buildspec-release.yml`
   - changed package publish set is resolved from signed release commit diff
     (`HEAD^..HEAD`) to prevent empty selective publish runs.
   - package uploads are pinned to CodeArtifact (`twine --repository codeartifact`).
   - default image build target:
     `apps/nova_file_api_service/Dockerfile`
   - CodeBuild inputs:
     `CODEARTIFACT_DOMAIN`, `CODEARTIFACT_REPOSITORY`,
     and ECR target (`ECR_REPOSITORY_URI` or `ECR_REPOSITORY_NAME`)
   - exported variables:
     `IMAGE_DIGEST`, `PUBLISHED_PACKAGES`,
     `RELEASE_MANIFEST_SHA256`, `CHANGED_UNITS`

## Documentation Map

- Requirements: `docs/architecture/requirements.md`
- ADR index: `docs/architecture/adr/index.md`
- SPEC index: `docs/architecture/spec/index.md`
- Execution plan: `docs/plan/PLAN.md`
- Subplans: `docs/plan/subplans/`
- Trigger prompts: `docs/plan/triggers/`
- Release notes: `docs/plan/release/RELEASE-NOTES-2026-02-12.md`
- Hard-cutover checklist: `docs/plan/release/HARD-CUTOVER-CHECKLIST.md`
- Non-prod live validation runbook:
  `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- Version manifest:
  `docs/plan/release/RELEASE-VERSION-MANIFEST.md`
- Release policy:
  `docs/plan/release/RELEASE-POLICY.md`
- Release runbook:
  `docs/plan/release/RELEASE-RUNBOOK.md`
