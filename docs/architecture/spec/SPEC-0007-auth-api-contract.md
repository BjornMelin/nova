---
Spec: 0007
Title: Auth API Contract
Status: Active
Version: 1.0
Date: 2026-02-12
Related:
  - "[SPEC-0006: JWT/OIDC verification and principal mapping](./SPEC-0006-jwt-oidc-verification-and-principal-mapping.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[ADR-0005: Add dedicated aws-auth-api service while keeping local verification default](../adr/ADR-0005-add-dedicated-aws-auth-api-service.md)"
References:
  - "[RFC 7662 OAuth Token Introspection](https://www.rfc-editor.org/rfc/rfc7662)"
  - "[RFC 6750 Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750)"
  - "[RFC 8725 JWT BCP](https://datatracker.ietf.org/doc/html/rfc8725)"
  - "[AWS ECS load balancer health checks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/load-balancer-healthcheck.html)"
---

## 1. Scope

This specification defines the HTTP contract for the dedicated `aws-auth-api` service.

The service provides:

- token verification for signed JWT/OIDC access tokens
- optional token introspection for opaque-token use cases
- health endpoint for deployment/runtime gates

`aws-file-api` MUST keep local JWT verification as the default behavior.
Remote `aws-auth-api` mode is optional and configuration-driven.

## 2. Endpoint contract

### 2.1 POST `/v1/token/verify`

Purpose: verify an access token and return a normalized principal.

Request body (`application/json`):

- `access_token`: string, required
- `required_scopes`: string array, optional
- `required_permissions`: string array, optional

Response `200`:

- `active`: boolean (`true` for successful verification)
- `principal`: normalized identity object
- `token`: sanitized token metadata (`iss`, `aud`, `sub`, `exp`, `iat`, `nbf`, `jti` when present)

Failure behavior:

- `401` for authentication failures (missing/invalid/expired token, invalid issuer/audience, etc.)
- `403` for authorization failures (insufficient scope/permissions)
- `401` responses SHOULD include RFC 6750-compatible `WWW-Authenticate`

### 2.2 POST `/v1/token/introspect` (optional mode)

Purpose: return RFC 7662-style token activity and metadata, primarily for opaque tokens.

Request requirements:

- MUST accept `application/x-www-form-urlencoded`
- MUST support:
  - `token` (required)
  - `token_type_hint` (optional)

Response requirements:

- On valid and active token query: `200` with `{"active": true, ...}`
- On properly authorized query for inactive/unknown token: `200` with `{"active": false}`
- Caller auth failure to introspection endpoint: `401` per RFC 7662

When introspection mode is disabled, deployments MAY omit this route.
Clients MUST treat `404` or `501` as "introspection disabled".

### 2.3 GET `/healthz`

Purpose: liveness/readiness gate for ECS/ALB.

Response `200` MUST include:

- `status`: `"ok"`
- `service`: `"aws-auth-api"`
- `request_id`: string

Health checks SHOULD be lightweight and MUST NOT require external token provider calls.

## 3. Principal normalization contract

`principal` in verify responses MUST contain:

- `subject`
- `scope_id`
- `scopes` (array)
- `permissions` (array)
- `tenant_id` or `org_id` when available

`scope_id` derivation order:

1. configured trusted tenant/org claim
2. `sub`

Client-provided identity hints MUST NOT override trusted verified claims.

## 4. Error envelope contract

All non-2xx responses MUST use:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {},
    "request_id": "string"
  }
}
```

Recommended error codes:

- `invalid_request`
- `missing_token`
- `invalid_token`
- `token_expired`
- `token_not_yet_valid`
- `invalid_issuer`
- `invalid_audience`
- `insufficient_scope`
- `insufficient_permissions`
- `introspection_disabled`
- `upstream_timeout`
- `upstream_unavailable`
- `internal_error`

## 5. Security and operations requirements

- Transport MUST use TLS.
- Introspection endpoint MUST require caller authentication to prevent token scanning.
- Token values and authorization headers MUST NOT be logged.
- Structured logs MUST include `request_id`.
- Verification policy MUST follow `SPEC-0006` and use canonical OIDC/JWT controls.

## 6. Integration requirements

When `aws-file-api` remote auth mode is enabled:

- verification failures or connectivity failures to `aws-auth-api` MUST fail closed
- auth mode MUST remain explicit and configuration-driven
- local verification mode MUST remain fully supported

## 7. Test requirements

Minimum coverage:

- verify success path with normalized principal output
- `401` and `403` mappings with stable error codes
- RFC 6750 `WWW-Authenticate` header behavior for `401`
- introspection active/inactive behavior (`200` responses)
- introspection caller-auth failure behavior (`401`)
- introspection disabled behavior (`404` or `501`)
- `/healthz` success behavior and response shape

## 8. Traceability

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [IR-0003](../requirements.md#ir-0003-optional-remote-auth-service)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
- [NFR-0003](../requirements.md#nfr-0003-operability)
