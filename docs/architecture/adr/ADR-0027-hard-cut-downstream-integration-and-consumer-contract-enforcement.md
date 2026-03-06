---
ADR: 0027
Title: Hard-cut downstream integration and consumer contract enforcement
Status: Accepted
Version: 1.0
Date: 2026-03-04
Related:
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](./ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
  - "[SPEC-0021: Downstream hard-cut integration and consumer validation contract](../spec/SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md)"
  - "[SPEC-0016: Hard-cut v1 route contract and route-literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
---

## Summary

Downstream integrations are part of the hard-cut contract surface. Consumer repos
must use canonical `/v1/*` runtime routes, adopt reusable validation workflow
APIs, and keep consumer examples synchronized with active Nova contract schemas.

## Context

Nova runtime route hard cut removed legacy route families from active contracts.
Consumer repositories can still drift unless the downstream integration layer is
also managed as a contract-governed authority surface.

## Decision

1. Downstream consumer route configuration is contract-governed and release-blocking.
2. Consumer integration examples under `docs/clients/**` are active authority
   artifacts, not optional guidance.
3. Post-deploy validation contracts must check both:
   - canonical route reachability (`/v1/*` + `/metrics/summary`), and
   - required legacy route `404` behavior.
4. Consumer workflow usage must pin reusable workflow references to `@v1` for
   stable channels and `@v1.x.y`/SHA for production immutability.

## Consequences

### Positive

- Removes ambiguity between runtime contract and downstream integration behavior.
- Keeps cross-repo migration and conformance evidence auditable.
- Prevents legacy-route regressions from re-entering through consumers.

### Trade-offs

- Increases documentation and schema synchronization burden for consumer-facing changes.
- Requires stricter CI checks for docs/clients contract drift.

## Explicit non-decisions

- No backward-compatibility aliases in runtime to support stale consumers.
- No unmanaged downstream "best effort" route-policy interpretation.

## Changelog

- 2026-03-04: Accepted downstream hard-cut integration authority decision.
