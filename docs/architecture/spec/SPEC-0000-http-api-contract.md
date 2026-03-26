---
Spec: 0000
Title: HTTP API Contract
Status: Active
Version: 2.2
Date: 2026-03-20
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
- File API request and response bodies use `application/json`.

Only canonical `/v1/*` routes and `/metrics/summary` are part of the active
runtime contract.

## 3. Endpoints

### 3.1 File-transfer control plane

- `POST /v1/transfers/uploads/initiate`
- `POST /v1/transfers/uploads/sign-parts`
- `POST /v1/transfers/uploads/complete`
- `POST /v1/transfers/uploads/abort`
- `POST /v1/transfers/downloads/presign`

### 3.2 Async jobs

- `POST /v1/exports`
- `GET /v1/exports`
- `GET /v1/exports/{export_id}`
- `POST /v1/exports/{export_id}/cancel`

### 3.3 Capability and release endpoints

- `GET /v1/capabilities`
- `POST /v1/resources/plan`
- `GET /v1/releases/info`

### 3.4 Operational

- `GET /v1/health/live`
- `GET /v1/health/ready`
- `GET /metrics/summary`

## 4. Non-canonical routes (normative)

Any route outside section 3 is not part of the contract and MUST return `404`.

## 5. Export workflow semantics

`POST /v1/exports` failure semantics:

- Queue publish failure MUST return `503`.
- Queue publish failure MUST return `error.code = "queue_unavailable"`.
- Failed enqueue attempts MUST NOT be replay-cached by idempotency storage.
- In-memory queue mode MUST honor `process_immediately`; when disabled,
  enqueue returns `queued` and MUST NOT auto-transition to `succeeded`.

Worker result-update transition semantics:

- `queued -> queued|validating|succeeded|failed|cancelled`
- `queued -> succeeded` is allowed for atomic worker completion across
  backends; in-memory `process_immediately` simulation currently transitions
  via `validating -> copying -> finalizing -> succeeded`.
- `validating -> validating|copying|succeeded|failed|cancelled`
- `copying -> copying|finalizing|succeeded|failed|cancelled`
- `finalizing -> finalizing|succeeded|failed|cancelled`
- terminal states (`succeeded|failed|cancelled`) allow same-state idempotent
  updates only.
- `status = succeeded` updates MUST clear `error` to `null`.
- invalid transition MUST return `409` with `error.code = "conflict"`.

## 6. Idempotency requirements

`POST /v1/transfers/uploads/initiate` and `POST /v1/exports` MUST support
idempotent retries via `Idempotency-Key` header.

- Repeated request with same key and same payload MUST replay the original
  response.
- Reuse of key with a different payload MUST return `409` with
  `error.code = "idempotency_conflict"`.
- Idempotency storage MUST be operation-based and independent from
  non-canonical route strings.

## 7. Scope and key rules

- Keys are server-generated.
- Follow-up operations MUST validate key ownership and allowed prefix.
- Trusted principal-derived scope MUST be used for scope-bound authorization.
- Public clients MUST NOT provide `session_id`, `X-Session-Id`, or `X-Scope-Id`
  as authorization surrogates.

## 8. Authentication and authorization semantics

Public runtime expectations:

- In-process bearer JWT verification is the active public authentication
  contract.
- `Authorization: Bearer <token>` is required.
- `401` for authentication failures, `403` for authorization failures.
- `401` MUST include RFC 6750-compatible
  `WWW-Authenticate: Bearer ...` header; header generation failures MUST fail
  closed.
- Scope and tenancy MUST be derived from verified claims in the authenticated
  `Principal`.
- `session_id`, `X-Session-Id`, and `X-Scope-Id` are not part of the public
  authentication contract and MUST NOT influence authorization behavior.

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
- `operationId` values MUST be unique across operations and stable across
  regeneration; current runtime values are explicit lowercase snake_case
  literals frozen by the runtime packages.
- SDK-facing semantic tags are the intended grouping model
  (`transfers`, `jobs`, `platform`, `ops`, and `health`), while
  current runtime schemas may still include implementation-owned tags such as
  `v1`.
- Custom request-body `$ref` values introduced via OpenAPI overrides MUST
  resolve to named schemas under `components.schemas`.

## 11. Traceability

- [FR-0000](../requirements.md#fr-0000-file-transfer-control-plane-endpoints)
- [FR-0001](../requirements.md#fr-0001-async-job-endpoints-and-orchestration)
- [FR-0002](../requirements.md#fr-0002-operational-endpoints)
- [FR-0004](../requirements.md#fr-0004-idempotency-for-mutation-entrypoints)
- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
