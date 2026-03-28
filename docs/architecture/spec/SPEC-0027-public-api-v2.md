# SPEC-0027 -- Public API v2

> **Implementation state:** Implemented in the current repository baseline as the active public API contract.

## Summary

Public API v2 exposes only explicit transfer and export workflow resources under bearer JWT auth.

## Authentication

- bearer JWT only
- no session-based auth
- no same-origin auth contract
- optional route-level JWT authorizer in API Gateway
- app-level authorization remains authoritative

## Resource model

### Uploads / transfers

- create upload intent
- create multipart upload intent
- sign multipart parts
- inspect multipart state
- complete multipart upload
- abort multipart upload

### Exports

- create export
- get export
- list exports
- optionally cancel export if the workflow semantics justify it

## Error model

- one canonical JSON error envelope
- correlation/request ID included
- typed validation errors
- explicit 401 / 403 / 404 / 409 / 422 / 429 / 5xx models

## OpenAPI rules

- no hand-built auth/session security schemes
- use native FastAPI `Security` and `responses=...`
- keep only minimal OpenAPI post-processing if a real generator gap remains
