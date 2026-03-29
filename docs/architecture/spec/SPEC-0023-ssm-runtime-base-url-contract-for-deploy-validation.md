---
Spec: 0023
Title: Historical SSM runtime base-url contract for deploy validation
Status: Historical
Version: 1.2
Date: 2026-03-05
Related:
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0016: Hard-cut v1 route contract and route-literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[ADR-0029: Historical SSM runtime base URL authority for deploy validation](../adr/ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md)"
---

## 1. Scope

Records the retired SSM-based base-url contract for deploy validation. The
current workflow surface accepts the validation base URL explicitly, and the
authenticated AWS account audited for this branch does not contain
`/nova/*/base-url` parameters.

## 2. Canonical SSM parameter path contract

Historical validation base URLs used this convention:

- `/nova/dev/{service}/base-url`
- `/nova/prod/{service}/base-url`

Where `{service}` is the canonical runtime service identifier.

Historical stack ownership:

- `/nova/dev/{service}/base-url` MUST be managed by exactly one stack:
  `${PROJECT}-ci-dev-service-base-url`.
- `/nova/prod/{service}/base-url` MUST be managed by exactly one stack:
  `${PROJECT}-ci-prod-service-base-url`.
- Additional stacks managing the same parameter paths are prohibited.

## 3. Value constraints

1. Base URL values were required to be HTTPS (`https://…`).
2. Values were required to be environment-appropriate and routable to the deployed public
   REST API URL for the runtime service and MUST resolve to the canonical
   custom-domain value exported as `NovaPublicBaseUrl`.
3. Non-HTTPS and placeholder endpoints were invalid for release validation gates.

## 4. CI/CD integration contract

1. Validation workflows and pipeline validation actions were intended to use base URLs
   sourced from SSM authority values (directly or via operator-resolved export),
   where the marker value is published from the canonical runtime stack output.
2. Deploy validation inputs for `DevServiceBaseUrl` and `ProdServiceBaseUrl`
   MUST satisfy HTTPS constraints.
3. Runbooks and scripts must document how base URLs are sourced and verified.
4. CI control-plane stack names for base-url markers must be treated as
   reserved ownership identifiers.

## 5. Evidence contract

Release evidence MUST include:

1. SSM parameter paths used for base URL resolution.
2. Resolved dev/prod base URL values used for validation.
3. Validation reports generated from those resolved URLs.

## 6. Acceptance criteria

1. Template contracts constrain deploy validation base URL inputs to HTTPS.
2. Runbooks include explicit SSM source/provenance steps.
3. Contract tests verify template + runbook + schema alignment.
4. Troubleshooting runbooks include recovery flow for deleted/drifted
   `AWS::SSM::Parameter` resources in base-url marker stacks.

## 7. Traceability

- [FR-0013](../requirements.md#fr-0013-ssm-runtime-base-url-authority-for-deploy-validation)
- [NFR-0109](../requirements.md#nfr-0109-runtime-base-url-integrity-and-provenance)
- [IR-0013](../requirements.md#ir-0013-ssm-base-url-source-of-truth-for-release-validation)
