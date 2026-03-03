# nova runtime

![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-0.129%2B-009688?logo=fastapi&logoColor=white) ![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1-6BA539?logo=openapiinitiative&logoColor=white)

FastAPI control-plane runtime for direct-to-S3 uploads/downloads and async job
orchestration. The service returns presigned metadata and job state; it does not
proxy file bytes.

## Canonical Contract

Active route authority is hard-cut canonical `/v1/*` plus `/metrics/summary`:

- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `docs/architecture/spec/SPEC-0000-http-api-contract.md`
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`

Topology and release-delivery authority:

- `docs/architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md`

Only canonical `/v1/*` routes and `/metrics/summary` are valid in active
contracts and operator runbooks.

## Runtime Capability Families

- Transfer orchestration: `/v1/transfers/*`
- Async job control plane: `/v1/jobs*`
- Internal worker update path: `/v1/internal/jobs/{job_id}/result`
- Capability/release discovery: `/v1/capabilities`, `/v1/resources/plan`,
  `/v1/releases/info`
- Operational health: `/v1/health/live`, `/v1/health/ready`
- Metrics summary: `/metrics/summary`

For exact endpoint and payload contract details, use:

- `docs/architecture/spec/SPEC-0000-http-api-contract.md`
- OpenAPI schema from runtime code

## Runtime Invariants

- `POST /v1/jobs` publish failures return `503` with
  `error.code = "queue_unavailable"`.
- Failed enqueue responses are not idempotency replay cached.
- `/v1/health/ready` is dependency-scoped and fails on blank
  `FILE_TRANSFER_BUCKET`.
- `POST /v1/internal/jobs/{job_id}/result` with `status=succeeded` normalizes
  `error` to `null`.

## Local Development

```bash
source .venv/bin/activate && uv lock --check
source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .
source .venv/bin/activate && uv run mypy
source .venv/bin/activate && uv run pytest -q
```

Run generated-client contract smoke:

```bash
source .venv/bin/activate && \
uv run pytest -q packages/nova_file_api/tests/test_generated_client_smoke.py
```

Package/app metadata isolation builds:

```bash
source .venv/bin/activate && \
for p in packages/nova_file_api packages/nova_auth_api \
  packages/nova_dash_bridge apps/nova_file_api_service \
  apps/nova_auth_api_service; do uv build "$p"; done
```

## Release and Operations

Canonical runbook entrypoint:

- `docs/runbooks/README.md`

Key active release docs:

- `docs/plan/release/RELEASE-RUNBOOK.md`
- `docs/plan/release/RELEASE-POLICY.md`
- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- `docs/plan/release/HARD-CUTOVER-CHECKLIST.md`
- `docs/plan/release/RELEASE-VERSION-MANIFEST.md`

## Documentation Authority Map

Active docs:

- Product requirements: `docs/PRD.md`
- Requirements: `docs/architecture/requirements.md`
- ADR index: `docs/architecture/adr/index.md`
- SPEC index: `docs/architecture/spec/index.md`
- Plan index: `docs/plan/PLAN.md`

Historical docs:

- History index: `docs/plan/HISTORY-INDEX.md`
- Archive root: `docs/history/README.md`
- Archived release notes: `docs/history/2026-02-cutover/release/RELEASE-NOTES-2026-02-12.md`
