# nova-auth-api

Token verification and introspection package for the Nova runtime.

## Exposed endpoints

- `POST /v1/token/verify`
- `POST /v1/token/introspect`
- `GET /v1/health/live`
- `GET /v1/health/ready`

`POST /v1/token/introspect` accepts both `application/json` and
`application/x-www-form-urlencoded` request bodies.

## Internal structure

Besides the public factory function `create_app()`, the package exposes a
module-level ASGI app at `nova_auth_api.main:app` (implemented in `main.py`)
which can be used by process managers and deploy tooling.

The package splits runtime concerns into dedicated modules:

- `main.py`: Exposes the `nova_auth_api.main:app` entrypoint for process managers;
  use `create_app()` instead of this entrypoint for programmatic configuration.
- `routes/` for HTTP handlers
- `middleware.py` for request-id context
- `request_parsing.py` for dual-mode introspection payload parsing
- `exception_handlers.py` for canonical error envelopes
- `openapi.py` and `operation_ids.py` for stable OpenAPI emission.
