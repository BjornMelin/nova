---
SPEC: 0027
Title: Public API v2
Status: Implemented
Version: 1.0
Date: 2026-03-25
Related:
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[ADR-0033: Canonical serverless platform](../adr/ADR-0033-canonical-serverless-platform.md)"
  - "[ADR-0034: Eliminate auth service and session auth](../adr/ADR-0034-eliminate-auth-service-and-session-auth.md)"
  - "[SPEC-0000: HTTP API Contract](./superseded/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[GREENFIELD WAVE 2 Execution](../plan/GREENFIELD-WAVE-2-EXECUTION.md)"
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
- use native FastAPI `Security` and `responses=…`
- keep only minimal OpenAPI post-processing if a real generator gap remains
