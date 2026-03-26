---
Spec: 0021
Title: Downstream hard-cut integration and consumer validation contract
Status: Active
Version: 1.1
Date: 2026-03-20
Related:
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API Contract](./SPEC-0000-http-api-contract.md)"
  - "[ADR-0027: Hard-cut downstream integration and consumer contract enforcement](../adr/ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md)"
  - "[SPEC-0016: Hard-cut v1 route contract and route-literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[SPEC-0025: Reusable workflow integration contract](./SPEC-0025-reusable-workflow-integration-contract.md)"
---

## 1. Scope

Defines mandatory downstream consumer integration behavior for Nova hard-cut
route authority and cross-repo validation contracts.

## 2. Canonical downstream route contract

1. Consumer integrations MUST target canonical `/v1/transfers` and `/v1/exports`
   route families.
2. Consumer integrations MUST NOT reference legacy route families forbidden by
   `SPEC-0016` as active runtime routes.
3. Consumer route configuration defaults in downstream repos must match canonical
   literals.
4. Browser-backed consumers using `nova_dash_bridge` MUST forward bearer
   `Authorization` headers to canonical upload/job requests.
5. Downstream consumers MUST NOT send `session_id`, `X-Session-Id`, or
   `X-Scope-Id` as Nova public auth/scope inputs.

## 3. Validation contract

Post-deploy validation contracts MUST include both:

1. Canonical route checks (`/v1/*` + `/metrics/summary`) that verify non-`404`
   contract behavior.
2. Legacy route checks that verify required `404` responses.

## 4. Reusable workflow pinning contract

1. Stable integration channel uses reusable workflow reference `@v1`.
2. Production integrations MUST pin immutable tags (`@v1.x.y`) or commit SHA.
3. Consumer examples must document both stable and immutable pin strategies.

## 5. Documentation and evidence contract

1. `docs/clients/**` files are active authority for downstream workflow examples.
2. Consumer-facing schema/documentation updates are required in the same change
   set as workflow API contract changes.
3. Cross-repo conformance evidence for dash/rshiny/react-next is release-gating.
4. Consumer integration docs must keep the bearer-only bridge contract aligned
   with `SPEC-0027`.

## 6. Acceptance criteria

1. Downstream workflow examples pass contract-doc tests.
2. Consumer route defaults remain canonical-only.
3. Post-deploy validation artifacts prove canonical and legacy-404 assertions.
4. Active downstream docs do not describe retired session/header scope carriers
   as public contract inputs.

## 7. Traceability

- [FR-0011](../requirements.md#fr-0011-downstream-hard-cut-consumer-integration-contract)
- [NFR-0107](../requirements.md#nfr-0107-downstream-contract-doc-and-schema-synchronization)
- [IR-0011](../requirements.md#ir-0011-cross-repo-consumer-conformance-authority)
