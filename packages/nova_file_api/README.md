# nova-file-api

FastAPI control-plane package for file transfers and async jobs in the Nova runtime.

## Process entrypoint

Besides the public factory function `create_app()`, the package exposes a
module-level ASGI app at `nova_file_api.main:app` (implemented in `main.py`)
which is the canonical process-manager and container entrypoint.

## API surface

Primary contract endpoints:

- `POST /v1/transfers/uploads/initiate`
- `POST /v1/transfers/uploads/sign-parts`
- `POST /v1/transfers/uploads/complete`
- `POST /v1/transfers/uploads/abort`
- `POST /v1/transfers/downloads/presign`
- `POST /v1/jobs`
- `GET /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `POST /v1/jobs/{job_id}/cancel`
- `POST /v1/jobs/{job_id}/retry`
- `GET /v1/jobs/{job_id}/events` (poll response shape compatible with SSE consumers)
- `GET /v1/capabilities`
- `POST /v1/resources/plan`
- `GET /v1/releases/info`
- `GET /v1/health/live`
- `GET /v1/health/ready`
- `POST /v1/internal/jobs/{job_id}/result`
- `GET /metrics/summary`

Canonical runtime namespace is `/v1/*`; legacy `/api/*`, `/healthz`, and
`/readyz` routes are intentionally removed.
