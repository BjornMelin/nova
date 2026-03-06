---
Spec: 0007
Title: Auth API Contract
Status: Active
Version: 1.2
Date: 2026-03-06
Related:
  - "[SPEC-0006: JWT/OIDC verification and principal mapping](./SPEC-0006-jwt-oidc-verification-and-principal-mapping.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[ADR-0005: Add dedicated nova-auth-api service while keeping local verification default](../adr/ADR-0005-add-dedicated-nova-auth-api-service.md)"
References:
  - "[RFC 7662 OAuth Token Introspection](https://www.rfc-editor.org/rfc/rfc7662)"
  - "[RFC 6750 Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750)"
  - "[RFC 8725 JWT BCP](https://datatracker.ietf.org/doc/html/rfc8725)"
  - "[AWS ECS load balancer health checks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/load-balancer-healthcheck.html)"
---

## 1. Scope

This specification defines the HTTP contract for the dedicated `nova-auth-api` service.

The service provides:

- token verification for signed JWT/OIDC access tokens
- token introspection over the same verifier/principal-mapping path
- health endpoint for deployment/runtime gates

`nova-file-api` MUST keep local JWT verification as the default behavior.
Remote `nova-auth-api` mode is optional and configuration-driven.

## 2. Endpoint contract

### 2.1 POST `/v1/token/verify`

Purpose: verify an access token and return a normalized principal plus claims.

Request body (`application/json`):

- `access_token`: string, required
- `required_scopes`: string array, optional
- `required_permissions`: string array, optional

Response `200`:

- `principal`: normalized identity object derived from verified claims
- `claims`: verified claim set returned by the local verifier

Failure behavior:

- `401` for authentication failures (missing/invalid/expired token, invalid issuer/audience, etc.)
- `403` for authorization failures (insufficient scope/permissions)
- `401` responses SHOULD include RFC 6750-compatible `WWW-Authenticate`

### 2.2 POST `/v1/token/introspect`

Purpose: return token activity, normalized principal metadata, and claims while
retaining compatibility with RFC 7662-style form callers.

Request requirements:

- MUST accept `application/json`
- JSON request body MUST support:
  - `access_token` (required)
  - `required_scopes` (optional)
  - `required_permissions` (optional)
- MUST accept `application/x-www-form-urlencoded`
- form payload MUST support:
  - `token` (required compatibility alias for `access_token`)
  - `token_type_hint` (optional compatibility hint; accepted and ignored)
  - repeated `required_scopes` values (optional)
  - repeated `required_permissions` values (optional)

Response requirements:

- On valid token query: `200` with:
  - `active: true`
  - `principal`
  - `claims`
- Invalid/expired token queries return `401` with the canonical error
  envelope.
- Insufficient scope/permission checks return `403` with the canonical error
  envelope.

Clients MUST NOT rely on inactive `{"active": false}` responses or route
omission in the current implementation.

### 2.3 GET `/v1/health/live`

Purpose: process liveness only.

Response `200` MUST include:

- `status`: `"ok"`
- `service`: `"nova-auth-api"`
- `request_id`: string

Health checks SHOULD be lightweight and MUST NOT require external token provider calls.

### 2.4 GET `/v1/health/ready`

Purpose: readiness gate for ECS/ALB and downstream runtime dependencies.

Response `200` MUST include:

- `status`: `"ok"`
- `service`: `"nova-auth-api"`
- `request_id`: string

Failure behavior:

- `503` with the canonical error envelope when verifier/config state is unavailable
- readiness MUST remain lightweight and MUST NOT require external token provider calls

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

Common error codes in the current runtime:

- `invalid_request`
- `unauthorized`
- `forbidden`
- `invalid_token`
- `service_unavailable`
- `internal_error`

Verifier-specific token-validation codes such as `token_expired`,
`token_not_yet_valid`, `invalid_issuer`, or `invalid_audience` MAY be surfaced
when provided by the OIDC verifier dependency.

## 5. Security and operations requirements

- Transport MUST use TLS.
- Introspection endpoint MUST require caller authentication to prevent token scanning.
- Token values and authorization headers MUST NOT be logged.
- Structured logs MUST include `request_id`.
- Verification policy MUST follow `SPEC-0006` and use canonical OIDC/JWT controls.

## 6. Integration requirements

When `nova-file-api` remote auth mode is enabled:

- verification failures or connectivity failures to `nova-auth-api` MUST fail closed
- auth mode MUST remain explicit and configuration-driven
- local verification mode MUST remain fully supported

## 7. Test requirements

Minimum coverage:

- verify success path with normalized principal output
- `401` and `403` mappings with stable error codes
- RFC 6750 `WWW-Authenticate` header behavior for `401`
- introspection JSON success behavior (`200`)
- introspection RFC 7662 form compatibility behavior (`200`)
- introspection invalid-token behavior (`401`)
- introspection scope/permission failure behavior (`403`)
- `/v1/health/live` success behavior and response shape
- `/v1/health/ready` success and `503` behavior

## 8. Traceability

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [IR-0003](../requirements.md#ir-0003-optional-remote-auth-service)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
- [NFR-0003](../requirements.md#nfr-0003-operability)
