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

### Worker result-update contract

- `POST /api/jobs/{job_id}/result` is used by trusted worker
  paths to publish state updates.
- Worker updates must follow legal transitions:
  - `pending -> pending|running|succeeded|failed|canceled`
  - `running -> running|succeeded|failed|canceled`
  - terminal states (`succeeded|failed|canceled`) only allow idempotent
    same-state updates.
- Invalid transitions return `409` with `error.code = "conflict"`.

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
- `CACHE_SHARED_BACKEND_URL`
- `IDEMPOTENCY_ENABLED`

## API Base Paths

- Transfers: `/api/transfers`
- Jobs: `/api/jobs`

## Local Development

Run in repository root:

```bash
source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .
source .venv/bin/activate && uv run mypy
source .venv/bin/activate && uv run pytest -q
```

## OpenAPI Contract Smoke

Generated-client smoke coverage is enforced with:

```bash
source .venv/bin/activate && \
uv run pytest -q \
  packages/nova_file_api/tests/test_generated_client_smoke.py
```

The smoke test generates a Python client with `openapi-python-client` from the
runtime OpenAPI schema and verifies generated code compiles successfully.

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
