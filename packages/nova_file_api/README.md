# nova-file-api

FastAPI control-plane package for file transfers and export workflows in the Nova runtime.

## Process entrypoints

The package exposes two public app/runtime assembly seams:

- `create_app(runtime=…)` builds the FastAPI surface around one prebuilt
  `ApiRuntime` container.
- `create_managed_app()` builds the same FastAPI surface but lets app lifespan
  own runtime bootstrap and shutdown for local development and tooling.

Within that runtime, FastAPI routes stay boundary-only. Request-owned
idempotency, metrics, and activity orchestration lives in explicit
application-layer coordinators below the route layer, and those coordinators
delegate transfer/export domain work to `TransferService` and `ExportService`.
The live runtime container is stored only at `app.state.runtime`.

At the package root, `nova_file_api` re-exports both builders. There is no
settings-driven `create_app(…)` path.

The module-level ASGI app at `nova_file_api.main:app` uses
`create_managed_app()` for local development and tooling. The production Lambda
entrypoint is `nova_file_api.lambda_handler.handler`, which bootstraps one
process-reused `ApiRuntime` container explicitly and then runs Mangum with
lifespan disabled so warm Lambda processes reuse that container across
invocations. If another caller owns a FastAPI app with lifespan-managed
startup, that caller should construct `Mangum(app, lifespan="auto")` directly
instead of routing through Nova's canonical Lambda helper.

## Browser contract

Browser-accessible origins are configured with `ALLOWED_ORIGINS` (JSON array or
comma-delimited string). In local development, the app falls back to explicit
localhost origins for common browser ports.

## API surface

Primary contract endpoints:

- `POST /v1/transfers/uploads/initiate`
- `POST /v1/transfers/uploads/introspect`
- `POST /v1/transfers/uploads/sign-parts`
- `POST /v1/transfers/uploads/complete`
- `POST /v1/transfers/uploads/abort`
- `POST /v1/transfers/downloads/presign`
- `POST /v1/exports`
- `GET /v1/exports`
- `GET /v1/exports/{export_id}`
- `POST /v1/exports/{export_id}/cancel`
- `GET /v1/capabilities`
- `GET /v1/capabilities/transfers`
- `POST /v1/resources/plan`
- `GET /v1/releases/info`
- `GET /v1/health/live`
- `GET /v1/health/ready`
- `GET /metrics/summary`

Canonical runtime namespace is `/v1/*`; legacy `/api/*`, `/healthz`, and
`/readyz` routes are intentionally removed.
