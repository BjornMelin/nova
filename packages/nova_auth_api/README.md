# nova-auth-api

Token verification and introspection package for the Nova runtime.

## Exposed endpoints

- `POST /v1/token/verify`
- `POST /v1/token/introspect`
- `GET /v1/health/live`
- `GET /v1/health/ready`

`POST /v1/token/introspect` accepts both `application/json` and
`application/x-www-form-urlencoded` request bodies.
