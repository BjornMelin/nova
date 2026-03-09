---
Spec: 0021
Title: Downstream hard-cut integration and consumer validation contract
Status: Active
Version: 1.0
Date: 2026-03-04
Related:
  - "[ADR-0027: Hard-cut downstream integration and consumer contract enforcement](../adr/ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md)"
  - "[SPEC-0016: Hard-cut v1 route contract and route-literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[SPEC-0025: Reusable workflow integration contract](./SPEC-0025-reusable-workflow-integration-contract.md)"
---

## 1. Scope

Defines mandatory downstream consumer integration behavior for Nova hard-cut
route authority and cross-repo validation contracts.

## 2. Canonical downstream route contract

1. Consumer integrations MUST target canonical `/v1/transfers` and `/v1/jobs`
   route families.
2. Consumer integrations MUST NOT reference legacy route families forbidden by
   `SPEC-0016` as active runtime routes.
3. Consumer route configuration defaults in downstream repos must match canonical
   literals.

## 3. Validation contract

Post-deploy validation contracts MUST include both:

1. Canonical route checks (`/v1/*` + `/metrics/summary`) that verify non-`404`
   contract behavior.
2. Legacy route checks that verify required `404` responses.

## 4. Reusable workflow reference contract

1. Stable major tags such as `@v1` are the published compatibility channel for
   downstream consumers.
2. Committed consumer workflow examples MUST use immutable release tags such as
   `@v1.x.y`.
3. Production and high-assurance integrations MUST pin immutable release tags
   or exact commit SHAs.
4. Consumer docs MUST NOT publish branch refs such as `@main` as supported
   integration references.

## 5. Documentation and evidence contract

1. `docs/clients/**` files are active authority for downstream workflow examples.
2. Consumer-facing schema/documentation updates are required in the same change
   set as workflow API contract changes.
3. Cross-repo conformance evidence for dash/rshiny/react-next is release-gating.

## 6. Acceptance criteria

1. Downstream workflow examples pass contract-doc tests.
2. Consumer route defaults remain canonical-only.
3. Post-deploy validation artifacts prove canonical and legacy-404 assertions.
4. Consumer guidance distinguishes major-tag onboarding from immutable
   production pinning.

## 7. Traceability

- [FR-0011](../requirements.md#fr-0011-downstream-hard-cut-consumer-integration-contract)
- [NFR-0107](../requirements.md#nfr-0107-downstream-contract-doc-and-schema-synchronization)
- [IR-0011](../requirements.md#ir-0011-cross-repo-consumer-conformance-authority)
