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

The package keeps `create_app()` as the public factory surface and splits
runtime concerns into dedicated modules:

- `routes/` for HTTP handlers
- `middleware.py` for request-id context
- `request_parsing.py` for dual-mode introspection payload parsing
- `exception_handlers.py` for canonical error envelopes
- `openapi.py` and `operation_ids.py` for stable OpenAPI emission

The package also exposes a loadable module-level ASGI app at
`nova_auth_api.main:app` for process managers and deployment tooling.
Prefer `create_app()` when constructing a configured app in Python code.
