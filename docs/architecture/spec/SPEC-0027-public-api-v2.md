---
SPEC: 0027
Title: Public API v2
Status: Implemented
Version: 1.0
Date: 2026-03-25
Related:
  - "[ADR-0033: Canonical serverless platform](../adr/ADR-0033-canonical-serverless-platform.md)"
  - "[ADR-0034: Eliminate auth service and session auth](../adr/ADR-0034-eliminate-auth-service-and-session-auth.md)"
---

## Summary

Public API v2 exposes only explicit transfer and export workflow resources under bearer JWT auth.

## Authentication

- bearer JWT only
- no session-based auth
- no same-origin auth contract
- Regional REST API ingress provides transport, direct Regional WAF, one
  canonical custom domain, and logging only. The default `execute-api`
  endpoint is disabled.
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
