---
ADR: 0023
Title: Hard cut to a single canonical /v1 API surface
Status: Accepted
Version: 1.0
Date: 2026-03-03
Related:
  - "[ADR-0015: Nova API platform final hosting and deployment architecture (2026)](./ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md)"
  - "[SPEC-0000: HTTP API Contract](../spec/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0015: Nova API platform final topology and delivery contract](../spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md)"
  - "[SPEC-0016: v1 route namespace and literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[RFC 9745: The Deprecation HTTP Response Header Field](https://www.rfc-editor.org/rfc/rfc9745.html)"
  - "[RFC 8594: The Sunset HTTP Header Field](https://www.rfc-editor.org/rfc/rfc8594.html)"
---

## Summary

Adopt a pre-deployment hard cut to one public API namespace: `/v1/*`.
Prior non-canonical runtime route families are removed in the same execution
wave.

## Context

The repository had multi-namespace route entropy that increased maintenance
cost, contract ambiguity, and regression risk. Breaking changes are explicitly
allowed for this release wave.

## Decision

1. Hard cut now with no sunset window.
2. Canonical runtime namespace is `/v1/*` with no alternate namespace aliases.
3. Worker update endpoint is internal-only at
   `/v1/internal/jobs/{job_id}/result`.
4. Health/readiness standardize to `/v1/health/live` and
   `/v1/health/ready`.
5. Observability summary remains non-versioned at `/metrics/summary`.
6. Removed routes: all non-canonical pre-cutover route families and the
   retired dedicated-auth route surface.

### Why canonical `/v1/*` namespace

- It creates one clean canonical client surface.
- It avoids preserving deprecated namespace semantics in new integrations.
- It keeps route contracts shorter while retaining explicit versioning.
- It removes namespace ambiguity in docs, generated SDKs, and conformance
  lanes.

## Weighted scoring (decision framework)

| Decision | Score (/10) |
| --- | ---: |
| Hard cut now (no sunset window) | 9.35-9.64 |
| Canonical namespace `/v1/*` | 9.2 |
| Internal worker endpoint `/v1/internal/jobs/{job_id}/result` | 9.1 |
| Health standardization `/v1/health/live`, `/v1/health/ready` | 9.3 |
| Non-versioned `/metrics/summary` | 9.0 |

Only options >=9.0 are accepted.

## Consequences

### Positive

- Single API contract surface.
- Lower cognitive load for runtime and consumers.
- Simpler CI policy and conformance validation.

### Trade-offs

- Existing pre-cutover callers must migrate immediately.
- Historical docs must be explicitly marked superseded where they describe
  dual-route authority.

## Supersession notes

- Supersedes route authority language that kept non-canonical namespaces
  operational as a first-class contract surface.
- `SPEC-0000`, `SPEC-0015`, and `SPEC-0016` are updated to reflect the hard cut
  contract.

## Explicit non-decisions

- No compatibility alias routes.
- No alternate version namespace introduction.
- No deprecation/sunset response headers required for this pre-deploy hard cut.
- No naming migration of `POST /v1/resources/plan` to `/v1/resource-plans` in
  this wave.
- No naming migration of `GET /v1/releases/info` to `/v1/releases` in this
  wave.
- No move of health endpoints to root (`/health/*`) in this wave; canonical
  health remains under `/v1/health/*`.

## Changelog

- 2026-03-03: Accepted hard-cut canonical route-surface decision.
