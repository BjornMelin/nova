---
Spec: 0027
Title: Public API v2
Status: Active
Version: 1.0
Date: 2026-03-25
Supersedes: "[SPEC-0027: Public HTTP contract revision and bearer auth (superseded)](./superseded/SPEC-0027-public-http-contract-revision-and-bearer-auth.md)"
Related:
  - "[requirements-wave-2.md](../requirements-wave-2.md)"
  - "[ADR-0034: Eliminate auth service and session auth](../adr/ADR-0034-eliminate-auth-service-and-session-auth.md)"
  - "[ADR-0035: Replace generic jobs with export workflows](../adr/ADR-0035-replace-generic-jobs-with-export-workflows.md)"
  - "[Breaking changes v2](../../contracts/BREAKING-CHANGES-V2.md)"
References:
  - "[Canonical target state (2026-04)](../../overview/CANONICAL-TARGET-2026-04.md)"
  - "[Green-field wave 2 execution plan](../../plan/GREENFIELD-WAVE-2-EXECUTION.md)"
---

## 1. Purpose

Define the approved target-state public HTTP contract for Nova after the wave-2
hard cut. This specification replaces the generic jobs and session-auth era
public contract with explicit transfer and export workflow resources under one
bearer-JWT-only auth model.

## 2. Scope

- Public transfer/upload resources remain part of the control-plane API.
- Durable async work is exposed as explicit export workflow resources.
- This spec focuses on the resource model and auth/contract shape for the next
  hard cut rather than describing the already-deployed baseline.

## 3. Authentication

- Public callers authenticate with bearer JWT only.
- Session or same-origin auth is not part of the approved target-state public
  contract.
- API Gateway JWT authorizers may be used for coarse route gating, but
  application-level authorization remains authoritative.

## 4. Resource model

### 4.1 Uploads / transfers

- create upload intent
- create multipart upload intent
- sign multipart parts
- inspect multipart state
- complete multipart upload
- abort multipart upload

### 4.2 Exports

- create export
- get export
- list exports
- optionally cancel export when workflow semantics support it

## 5. Error model

- one canonical JSON error envelope
- correlation/request ID included
- typed validation errors
- explicit 401 / 403 / 404 / 409 / 422 / 429 / 5xx models

## 6. OpenAPI rules

- use native FastAPI `Security(...)` and `responses=...`
- do not keep hand-built auth/session security schemes
- keep post-processing minimal and justified by a concrete generator gap
- generated SDKs must see explicit typed request/response shapes

## 7. Breaking changes explicitly accepted

- delete same-origin/session auth completely
- delete `X-Session-Id`, body `session_id`, and `X-Scope-Id`
- delete generic jobs from the public API
- replace generic jobs with explicit export resources

## 8. Traceability

- [Product requirements](../requirements-wave-2.md#product-requirements)
- [Architecture requirements](../requirements-wave-2.md#architecture-requirements)
- [Quality requirements](../requirements-wave-2.md#quality-requirements)
