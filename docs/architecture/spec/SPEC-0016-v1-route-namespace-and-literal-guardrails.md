---
Spec: 0016
Title: Hard-cut v1 route contract and route-literal guardrails
Status: Active
Version: 2.0
Date: 2026-03-03
Related:
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API Contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0015: Nova API platform final topology and delivery contract](./SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md)"
---

## 1. Scope

Defines the canonical runtime route set after hard cut and the CI guardrails
that prevent reintroduction of legacy route entropy.

## 2. Canonical route policy

1. Public runtime routes MUST use `/v1/*` except `/metrics/summary`.
2. Internal worker update route MUST use `/v1/internal/*`.
3. Any route outside canonical `/v1/*` and `/metrics/summary` MUST NOT be
   exposed.

## 3. Canonical route set (normative)

Public runtime routes:

- `POST /v1/transfers/uploads/initiate`
- `POST /v1/transfers/uploads/sign-parts`
- `POST /v1/transfers/uploads/complete`
- `POST /v1/transfers/uploads/abort`
- `POST /v1/transfers/downloads/presign`
- `POST /v1/jobs`
- `GET /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `POST /v1/jobs/{job_id}/cancel`
- `POST /v1/jobs/{job_id}/retry`
- `GET /v1/jobs/{job_id}/events`
- `GET /v1/capabilities`
- `POST /v1/resources/plan`
- `GET /v1/releases/info`
- `GET /v1/health/live`
- `GET /v1/health/ready`
- `GET /metrics/summary`

Internal-only route:

- `POST /v1/internal/jobs/{job_id}/result`

Auth service target routes:

- `POST /v1/token/verify`
- `POST /v1/token/introspect`
- `GET /v1/health/live`
- `GET /v1/health/ready`

Non-canonical runtime paths outside this set MUST return `404`.

## 4. CI guardrail requirements

`.github/workflows/ci.yml` MUST enforce:

1. Required literal checks for canonical route set above.
2. OpenAPI contract checks that every path is either `/metrics/summary` or
   starts with `/v1/`.
3. Route decorator structural checks in runtime router modules and app
   factories so resolved runtime paths are only `/v1/*` or
   `/metrics/summary`.
4. Failure on runtime source references to non-canonical route literals.
5. Unique OpenAPI `operationId` values.

## 5. Contract fixture and conformance requirements

1. `packages/contracts/fixtures/v1/README.md` MUST reference canonical
   `/v1/*` routes only.
2. Dash/Shiny/TypeScript conformance lane checks MUST align to v1 route
   literals and schema fixtures. The TypeScript lane MUST exercise the
   validation-free generated SDK clients against fixture-backed mock fetches.
3. Generated-client smoke tests MUST remain green against the canonical route
   set.

## 6. Acceptance criteria

1. Runtime exposes only canonical routes in section 3.
2. Non-canonical routes return `404`.
3. Enqueue failure and readiness invariants are preserved:
   - `queue_unavailable` remains `503` on enqueue publish failures.
   - readiness remains bucket-sensitive and matches the aggregate readiness
     contract defined in SPEC-0000 (health/readiness semantics).
   - `status=succeeded` worker updates normalize `error=null`.
4. CI fails on any legacy route reintroduction.

## 7. Traceability

- [FR-0000](../requirements.md#fr-0000-file-transfer-control-plane-endpoints)
- [FR-0001](../requirements.md#fr-0001-async-job-endpoints-and-orchestration)
- [FR-0002](../requirements.md#fr-0002-operational-endpoints)
- [FR-0004](../requirements.md#fr-0004-idempotency-for-mutation-entrypoints)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
