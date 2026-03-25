---
Spec: 0028
Title: Export workflow state machine
Status: Active
Version: 1.0
Date: 2026-03-25
Supersedes: "[SPEC-0028: Worker job lifecycle and direct result path (superseded)](./superseded/SPEC-0028-worker-job-lifecycle-and-direct-result-path.md)"
Related:
  - "[requirements-wave-2.md](../requirements-wave-2.md)"
  - "[ADR-0035: Replace generic jobs with export workflows](../adr/ADR-0035-replace-generic-jobs-with-export-workflows.md)"
  - "[SPEC-0027: Public API v2](./SPEC-0027-public-api-v2.md)"
  - "[Breaking changes v2](../../contracts/BREAKING-CHANGES-V2.md)"
References:
  - "[Canonical target state (2026-04)](../../overview/CANONICAL-TARGET-2026-04.md)"
  - "[Green-field wave 2 execution plan](../../plan/GREENFIELD-WAVE-2-EXECUTION.md)"
---

## 1. Purpose

Define the approved target-state workflow model for exports. Exports are durable
workflow resources with explicit states, explicit retry behavior, and explicit
operator-visible state ownership.

## 2. Workflow ownership

- Step Functions Standard is the workflow driver
- DynamoDB is the state/query model for the API
- the API never depends on an internal callback route to progress workflow
  state

## 3. States

- `queued`
- `validating`
- `copying`
- `finalizing`
- `succeeded`
- `failed`
- `cancelled` when supported by the workflow semantics

## 4. Inputs

- source upload bucket/key
- target export bucket/key
- file metadata
- requester principal / tenant / scope context
- idempotency key
- output constraints and retention policy

## 5. Failure and retry rules

- all task retries are explicit
- all failures are written to workflow state
- no hidden worker-only failure channel exists
- the workflow state model must remain queryable without depending on internal
  callback semantics

## 6. Query rules

- API reads export status from DynamoDB
- API may surface execution metadata links/ids for operators, but not as
  required client semantics
- clients interact with export resources, not worker internals

## 7. Traceability

- [Product requirements](../requirements-wave-2.md#product-requirements)
- [Architecture requirements](../requirements-wave-2.md#architecture-requirements)
- [Quality requirements](../requirements-wave-2.md#quality-requirements)
