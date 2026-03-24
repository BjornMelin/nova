---
ADR: 0029
Title: SSM runtime base URL authority for deploy validation
Status: Accepted
Version: 1.1
Date: 2026-03-05
Related:
  - "[ADR-0030: Native-CFN modular stack architecture for Nova infrastructure productization](./ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md)"
  - "[SPEC-0023: SSM runtime base-url contract for deploy validation](../spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md)"
  - "[SPEC-0024: CloudFormation module contract](../spec/SPEC-0024-cloudformation-module-contract.md)"
---

## Summary

Deploy validation base URLs are governed by an SSM-backed authority contract.
Operators and automation must source environment base URLs from canonical SSM
parameter paths, where the stored value is published from the runtime
CloudFront edge stack, and pass those values into deployment validation flows.

## Context

Pipeline validation quality depends on using correct environment URLs. Manual,
ad-hoc URL entry allows placeholder values and undermines gate evidence quality.

## Decision

1. Runtime validation base URLs are SSM-governed authority values.
2. Environment base URLs passed to CI/CD and validation workflows must be HTTPS
   and environment-scoped (`dev`/`prod`).
3. Release/runbook evidence must include provenance of base URL values used for
   validation gates.
4. Template and runbook contracts must stay synchronized for base URL sourcing.
5. Base-url parameters are single-owner resources managed only by the canonical
   CI control-plane marker stacks:
   `${PROJECT}-ci-dev-service-base-url` and
   `${PROJECT}-ci-prod-service-base-url`.
6. Release/runbook references for marker stack names must use this exact
   `${PROJECT}-ci-{dev,prod}-service-base-url` convention.

## Consequences

### Positive

- Improves reproducibility and auditability of validation gates.
- Reduces risk of validating against non-runtime placeholder endpoints.
- Strengthens release evidence quality for promotion controls.
- Prevents conflicting stack ownership of the same SSM parameter paths.

### Trade-offs

- Adds SSM parameter lifecycle management overhead.
- Requires additional operator and CI checks for URL provenance.
- Requires explicit drift-recovery procedures when parameter resources are
  deleted outside stack management.

## Explicit non-decisions

- No plaintext hardcoded endpoint values as authority source in active runbooks.
- No non-HTTPS base URL acceptance for deploy validation contracts.

## Changelog

- 2026-03-04: Accepted SSM-backed runtime base URL authority decision.
- 2026-03-05: Added explicit single-owner stack policy and drift-recovery
  governance note.
