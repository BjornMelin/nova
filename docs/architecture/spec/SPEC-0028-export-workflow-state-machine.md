---
SPEC: 0028
Title: Export workflow state machine
Status: Implemented
Version: 1.2
Date: 2026-04-08
Related:
  - "[ADR-0033: Canonical serverless platform](../adr/ADR-0033-canonical-serverless-platform.md)"
  - "[ADR-0035: Replace generic jobs with export workflows](../adr/ADR-0035-replace-generic-jobs-with-export-workflows.md)"
---

## Summary

Exports are durable workflow resources backed by Step Functions Standard and DynamoDB.
The workflow uses one of two internal copy lanes after validation:

- inline server-side copy for moderate objects
- queued multipart copy workers for larger objects

## States

- `queued`
- `validating`
- `copying`
- `finalizing`
- `succeeded`
- `failed`
- `cancelled` (optional)

## State ownership

- Step Functions execution is the workflow driver
- DynamoDB is the state/query model for the API
- the API never depends on an internal callback route to progress workflow state

## Inputs

- source upload bucket/key
- target export bucket/key
- file metadata
- requester principal / tenant / scope context
- idempotency key
- output constraints and retention policy
- internal copy-lane metadata such as worker threshold, multipart upload id,
  durable part-state location, and queue progress state

## Failure rules

- all task retries are explicit
- all failures are written to workflow state
- no hidden worker-only failure channel
- queued worker failures MUST either persist export failure in-band or remain
  observable on the normal SQS retry/DLQ path; the worker lane MUST NOT hide
  malformed-message failure modes behind silent retries
- canonical queued-worker messages MUST carry enough internal metadata in SQS
  message attributes to mark the active part or export terminal when the JSON
  body is malformed
- malformed queued-worker messages without recoverable SQS attributes MUST stay
  on the normal retry/DLQ path and MUST still emit unresolved-invalid and lag
  observability
- cancellation MUST stop the Step Functions execution, `cancelled` MUST remain
  authoritative over later fail/finalize attempts, and queued workers MUST
  check the export record before copying more parts
- inline copy MUST perform a post-copy cancellation fence and delete the copied
  export object before any success finalization path continues

## Query rules

- API reads export status from DynamoDB
- API can surface execution metadata links/ids for operators, but not as required client semantics
- internal queued-copy progress state does not create a second public export
  resource model
