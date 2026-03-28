# SPEC-0028 -- Export workflow state machine

> **Implementation state:** Approved target-state SPEC. It defines the explicit export resource model Codex should implement.

## Summary

Exports are durable workflow resources backed by Step Functions Standard and DynamoDB.

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

## Failure rules

- all task retries are explicit
- all failures are written to workflow state
- no hidden worker-only failure channel

## Query rules

- API reads export status from DynamoDB
- API can surface execution metadata links/ids for operators, but not as required client semantics
