---
Spec: 0000
Title: HTTP API Contract
Status: Active
Version: 1.7
Date: 2026-02-23
Related:
  - "[ADR-0000: FastAPI service decision](../adr/ADR-0000-fastapi-microservice.md)"
  - "[ADR-0006: Async orchestration with SQS + ECS worker](../adr/ADR-0006-async-orchestration-sqs-ecs-worker.md)"
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

## 2. Base paths and media type

- Transfer base path: `/api/transfers`
- Jobs base path: `/api/jobs`
- Content type: `application/json`

## 3. Endpoints

### 3.1 File-transfer control plane

- `POST /api/transfers/uploads/initiate`
- `POST /api/transfers/uploads/sign-parts`
- `POST /api/transfers/uploads/complete`
- `POST /api/transfers/uploads/abort`
- `POST /api/transfers/downloads/presign`

### 3.2 Async jobs

- `POST /api/jobs/enqueue`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/cancel`
- `POST /api/jobs/{job_id}/result` (worker/internal update)

`POST /api/jobs/enqueue` failure semantics:

- Queue publish failure MUST return `503`.
- Queue publish failure MUST return `error.code = "queue_unavailable"`.
- Failed enqueue attempts MUST NOT be replay-cached by idempotency storage.
- In-memory queue mode MUST honor `process_immediately`; when disabled, enqueue
  returns `pending` and MUST NOT auto-transition to `succeeded`.

`POST /api/jobs/{job_id}/result` transition semantics:

- `pending -> pending|running|succeeded|failed|canceled`
- `pending -> succeeded` is allowed for atomic worker completion across
  backends; in-memory `process_immediately` simulation currently transitions via
  `running` before `succeeded`.
- `running -> running|succeeded|failed|canceled`
- terminal states (`succeeded|failed|canceled`) allow same-state idempotent
  updates only.
- `status = succeeded` updates MUST clear `error` to `null`.
- invalid transition MUST return `409` with `error.code = "conflict"`.

### 3.3 Operational

- `GET /healthz`
- `GET /readyz`
- `GET /metrics/summary`

## 4. Idempotency requirements

`POST /api/transfers/uploads/initiate` and `POST /api/jobs/enqueue` MUST
support idempotent
retries via `Idempotency-Key` header.

- Repeated request with same key and same payload MUST replay the original
  response.
- Reuse of key with a different payload MUST return `409` with
  `error.code = "idempotency_conflict"`.

## 5. Scope and key rules

- Keys are server-generated.
- Follow-up operations MUST validate key ownership and allowed prefix.
- In JWT mode, trusted principal-derived scope MUST take precedence over
  client-provided session identifiers.

## 6. Authentication and authorization semantics

Supported auth modes:

- same-origin
- jwt-local
- jwt-remote (optional, fail-closed)

Same-origin expectations:

- Body-bearing routes may convey caller scope via `session_id` payload field.
- Body-less scope-bound routes (for example `GET /api/jobs/{job_id}`) must
  convey caller scope via trusted header (`X-Session-Id` or `X-Scope-Id`).
- When `X-Session-Id` and `X-Scope-Id` are both present, `X-Session-Id` takes
  precedence for scope binding.
- Differing `X-Session-Id` and `X-Scope-Id` values are not a protocol error;
  the request is evaluated using `X-Session-Id`.
- When `X-Session-Id` and body `session_id` are both present with differing
  values, request validation fails with `422` and
  `error.message = "conflicting session scope"`.
- When `X-Session-Id` is absent and `X-Scope-Id` plus body `session_id` are
  both present with differing values, authentication fails with `401` and
  `error.message = "conflicting session scope"`.

JWT mode expectations:

- `Authorization: Bearer <token>` is required.
- `401` for authentication failures, `403` for authorization failures.
- `401` MUST include RFC 6750-compatible `WWW-Authenticate: Bearer ...` header;
  header generation failures MUST fail closed (surface auth error or
  deterministic fallback challenge), per RFC 6750 §3.1.

## 7. Error envelope

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

## 8. Traceability

- [FR-0000](../requirements.md#fr-0000-file-transfer-control-plane-endpoints)
- [FR-0001](../requirements.md#fr-0001-async-job-endpoints-and-orchestration)
- [FR-0002](../requirements.md#fr-0002-operational-endpoints)
- [FR-0004](../requirements.md#fr-0004-idempotency-for-mutation-entrypoints)
- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
