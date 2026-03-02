# nova-file-api

FastAPI control-plane package for file transfers and async jobs in the Nova runtime.

## API surface

Primary contract endpoints:

- `POST /v1/jobs`
- `GET /v1/jobs`
- `GET /v1/jobs/{id}`
- `POST /v1/jobs/{id}/retry`
- `GET /v1/jobs/{id}/events` (poll response shape compatible with SSE consumers)
- `GET /v1/capabilities`
- `POST /v1/resources/plan`
- `GET /v1/releases/info`
- `GET /v1/health/live`
- `GET /v1/health/ready`

Legacy/compat endpoints remain under `/api/transfers/*`, `/api/jobs/*`, `/healthz`, `/readyz`.
