---
Spec: 0023
Title: SSM runtime base-url contract for deploy validation
Status: Active
Version: 1.1
Date: 2026-03-05
Related:
  - "[ADR-0029: SSM runtime base URL authority for deploy validation](../adr/ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md)"
  - "[SPEC-0017: CloudFormation module contract](./SPEC-0017-runtime-component-topology-and-ownership-contract.md)"
  - "[SPEC-0020: Rollout and validation strategy](./SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md)"
---

## 1. Scope

Defines the authority contract for runtime deploy-validation base URL values,
including SSM path conventions, URL constraints, and evidence requirements.

## 2. Canonical SSM parameter path contract

Validation base URLs MUST be sourced from parameter paths using this convention:

- `/nova/dev/{service}/base-url`
- `/nova/prod/{service}/base-url`

Where `{service}` is the canonical runtime service identifier.

Canonical stack ownership:

- `/nova/dev/{service}/base-url` MUST be managed by exactly one stack:
  `${PROJECT}-ci-dev-service-base-url`.
- `/nova/prod/{service}/base-url` MUST be managed by exactly one stack:
  `${PROJECT}-ci-prod-service-base-url`.
- Additional stacks managing the same parameter paths are prohibited.

## 3. Value constraints

1. Base URL values MUST be HTTPS (`https://...`).
2. Values MUST be environment-appropriate and routable to deployed runtime ALB
   endpoints.
3. Non-HTTPS and placeholder endpoints are invalid for release validation gates.

## 4. CI/CD integration contract

1. Validation workflows and pipeline validation actions MUST use base URLs
   sourced from SSM authority values (directly or via operator-resolved export).
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
