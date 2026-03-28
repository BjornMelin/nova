> **Superseded target draft**
>
> This draft was superseded before implementation by `../SPEC-0028-export-workflow-state-machine.md`.

---
Spec: 0028
Title: Worker job lifecycle and direct result path
Status: Superseded
Version: 1.0
Date: 2026-03-19
Related:
  - "[ADR-0035: Green-field worker direct result persistence](../adr/ADR-0035-worker-direct-result-persistence.md)"
  - "[SPEC-0008: Async jobs and worker orchestration](./SPEC-0008-async-jobs-and-worker-orchestration.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[requirements.md](../requirements.md)"
---

## 1. Purpose

Define the **target** worker and job lifecycle after removing the internal HTTP
result callback, and align queue and persistence semantics with
[ADR-0035](../adr/ADR-0035-worker-direct-result-persistence.md).

[SPEC-0008](./SPEC-0008-async-jobs-and-worker-orchestration.md) remains the
broader async jobs specification; this SPEC is the **normative overlay** for
result persistence path and related configuration removal.

## 2. Public job API surface (unchanged paths)

Async jobs remain managed through:

- `POST /v1/jobs`
- `GET /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `POST /v1/jobs/{job_id}/cancel`
- `POST /v1/jobs/{job_id}/retry`
- `GET /v1/jobs/{job_id}/events`

Canonical schemas remain owned by SPEC-0000 and runtime OpenAPI.

## 3. Job states

- `pending`
- `running`
- `succeeded`
- `failed`
- `canceled`

## 4. State transition rules

- The worker may transition `pending -> running` before doing work.
- Terminal transitions are written through **shared runtime services or
  repositories**, not through an HTTP callback into the API.
- Status-transition validation remains centralized and race-safe.
- `status = succeeded` updates **must** clear `error` to `null`.
- Invalid transitions **must** fail with `409` (`error.code = "conflict"`).

## 5. Queue semantics

- SQS remains the durable delivery path for AWS deployments.
- Poison messages are **not** silently acknowledged.
- Visibility-extension and DLQ semantics remain as specified in SPEC-0008.

## 6. Result update path

- **No** worker-to-API HTTP callback exists for job results.
- The worker updates job result state **directly** via shared code.
- Metrics and activity emission occur in the shared mutation path or adjacent
  worker orchestration, not via HTTP indirection.

## 7. Configuration contract

- `JOBS_API_BASE_URL` and worker HTTP callback token settings are **removed**
  from the target configuration surface when the direct persistence path is
  implemented.
- Remaining worker configuration covers queue, persistence, and runtime
  behavior only.

## 8. Traceability

- [GFR-R5](../requirements.md#gfr-r5--worker-must-not-self-call-the-api)
- [FR-0001](../requirements.md#fr-0001-async-job-endpoints-and-orchestration)

## Changelog

- 2026-03-19: Initial canonical SPEC; ports green-field pack SPEC-0002.
