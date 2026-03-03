---
Spec: 0000
Title: HTTP API Contract
Status: Active
Version: 2.0
Date: 2026-03-03
Related:
  - "[ADR-0000: FastAPI service decision](../adr/ADR-0000-fastapi-microservice.md)"
  - "[ADR-0006: Async orchestration with SQS + ECS worker](../adr/ADR-0006-async-orchestration-sqs-ecs-worker.md)"
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0015: Nova API platform final topology and delivery contract](./SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md)"
  - "[SPEC-0016: Hard-cut v1 route contract and route-literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[SPEC-0001: Security model](./SPEC-0001-security-model.md)"
  - "[SPEC-0008: Async jobs and worker orchestration](./SPEC-0008-async-jobs-and-worker-orchestration.md)"
  - "[SPEC-0009: Caching and idempotency](./SPEC-0009-caching-and-idempotency.md)"
References:
  - "[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)"
  - "[RFC 6750 Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750)"
---

## 1. Scope

Defines the external control-plane API for file-transfer orchestration and
related async jobs. The API does not transfer object bytes.

Hard-cut state (2026-03-03): runtime contract is canonical `/v1/*` plus
`/metrics/summary`.

## 2. Base paths and media type

- API base path: `/v1`
- Operational summary path: `/metrics/summary`
- Content type: `application/json`

Legacy `/api/*`, `/healthz`, and `/readyz` routes are removed.

## 3. Endpoints

### 3.1 File-transfer control plane

- `POST /v1/transfers/uploads/initiate`
- `POST /v1/transfers/uploads/sign-parts`
- `POST /v1/transfers/uploads/complete`
- `POST /v1/transfers/uploads/abort`
- `POST /v1/transfers/downloads/presign`

### 3.2 Async jobs

- `POST /v1/jobs`
- `GET /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `POST /v1/jobs/{job_id}/cancel`
- `POST /v1/jobs/{job_id}/retry`
- `GET /v1/jobs/{job_id}/events`
- `POST /v1/internal/jobs/{job_id}/result` (worker/internal update)

### 3.3 Capability and release endpoints

- `GET /v1/capabilities`
- `POST /v1/resources/plan`
- `GET /v1/releases/info`

### 3.4 Operational

- `GET /v1/health/live`
- `GET /v1/health/ready`
- `GET /metrics/summary`

## 4. Removed routes (normative)

The following routes are not part of the contract and MUST return `404`:

- all `/api/transfers/*`
- all `/api/jobs/*`
- `/healthz`
- `/readyz`
- all `/api/v1/*`

## 5. Job semantics

`POST /v1/jobs` failure semantics:

- Queue publish failure MUST return `503`.
- Queue publish failure MUST return `error.code = "queue_unavailable"`.
- Failed enqueue attempts MUST NOT be replay-cached by idempotency storage.
- In-memory queue mode MUST honor `process_immediately`; when disabled,
  enqueue returns `pending` and MUST NOT auto-transition to `succeeded`.

`POST /v1/internal/jobs/{job_id}/result` transition semantics:

- `pending -> pending|running|succeeded|failed|canceled`
- `pending -> succeeded` is allowed for atomic worker completion across
  backends; in-memory `process_immediately` simulation currently transitions
  via `running` before `succeeded`.
- `running -> running|succeeded|failed|canceled`
- terminal states (`succeeded|failed|canceled`) allow same-state idempotent
  updates only.
- `status = succeeded` updates MUST clear `error` to `null`.
- invalid transition MUST return `409` with `error.code = "conflict"`.

## 6. Idempotency requirements

`POST /v1/transfers/uploads/initiate` and `POST /v1/jobs` MUST support
idempotent retries via `Idempotency-Key` header.

- Repeated request with same key and same payload MUST replay the original
  response.
- Reuse of key with a different payload MUST return `409` with
  `error.code = "idempotency_conflict"`.
- Idempotency storage MUST be operation-based and independent from legacy
  removed route strings.

## 7. Scope and key rules

- Keys are server-generated.
- Follow-up operations MUST validate key ownership and allowed prefix.
- In JWT mode, trusted principal-derived scope MUST take precedence over
  client-provided session identifiers.

## 8. Authentication and authorization semantics

Supported auth modes:

- same-origin
- jwt-local
- jwt-remote (optional, fail-closed)

Same-origin expectations:

- Body-bearing routes may convey caller scope via `session_id` payload field.
- Body-less scope-bound routes (for example `GET /v1/jobs/{job_id}`) MUST
  convey caller scope via trusted header (`X-Session-Id` or `X-Scope-Id`).
- When `X-Session-Id` and `X-Scope-Id` are both present, `X-Session-Id` MUST take
  precedence for scope binding.
- Differing `X-Session-Id` and `X-Scope-Id` values are not a protocol error;
  the request is evaluated using `X-Session-Id`.
- When `X-Session-Id` and body `session_id` are both present with differing
  values, request validation MUST fail with `422` and
  `error.message = "conflicting session scope"`.
- When `X-Session-Id` is absent and `X-Scope-Id` plus body `session_id` are
  both present with differing values, authentication MUST fail with `401` and
  `error.message = "conflicting session scope"`.

JWT mode expectations:

- `Authorization: Bearer <token>` is required.
- `401` for authentication failures, `403` for authorization failures.
- `401` MUST include RFC 6750-compatible
  `WWW-Authenticate: Bearer ...` header; header generation failures MUST fail
  closed.
- In JWT mode, principal-derived scope MUST take precedence over
  client-provided `X-Session-Id`, `X-Scope-Id`, or body `session_id`.

## 9. Error envelope

All non-2xx responses MUST return:

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

Queue publication failures for async enqueue use:

- `status_code = 503`
- `error.code = "queue_unavailable"`

## 10. OpenAPI contract requirements

- OpenAPI 3.1 output from runtime code is the canonical machine contract.
- Paths MUST match section 3.
- `operationId` values MUST be unique across operations.

## 11. Traceability

- [FR-0000](../requirements.md#fr-0000-file-transfer-control-plane-endpoints)
- [FR-0001](../requirements.md#fr-0001-async-job-endpoints-and-orchestration)
- [FR-0002](../requirements.md#fr-0002-operational-endpoints)
- [FR-0004](../requirements.md#fr-0004-idempotency-for-mutation-entrypoints)
- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
