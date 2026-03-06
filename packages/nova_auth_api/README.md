# nova-auth-api

Token verification and introspection package for the Nova runtime.

## Exposed endpoints

- `POST /v1/token/verify`
- `POST /v1/token/introspect`
- `GET /v1/health/live`
- `GET /v1/health/ready`

## Request and response contract

### `POST /v1/token/verify`

- Request body: JSON `TokenVerifyRequest`
- Required field: `access_token`
- Optional fields: `required_scopes`, `required_permissions`
- Success response: `200` with normalized `principal` plus raw `claims`
- Failure envelope: canonical Nova auth error body with `error.code`,
  `error.message`, and structured `error.details`

### `POST /v1/token/introspect`

- Accepts JSON `TokenIntrospectRequest`
- Also accepts RFC 7662 style `application/x-www-form-urlencoded` payloads
  using `token` as the compatibility alias for `access_token`
- Optional form compatibility field: `token_type_hint` (accepted and ignored)
- Optional scope/permission checks are supported for both JSON and form payloads
- Success response: `200` with `active`, and when active, normalized
  `principal` plus raw `claims`
- Invalid or expired token responses use `401`; scope/permission failures use `403`

## Health semantics

- `GET /v1/health/live` is a process liveness probe.
- `GET /v1/health/ready` is a traffic-readiness probe for auth verification.
- Readiness returns `503 service_unavailable` when verifier/config state is not ready.
