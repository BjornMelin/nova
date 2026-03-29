---
ADR: 0029
Title: SSM runtime base URL authority for deploy validation
Status: Historical
Version: 1.2
Date: 2026-03-05
Related:
  - "[ADR-0033: Canonical serverless platform](./ADR-0033-canonical-serverless-platform.md)"
  - "[SPEC-0023: Historical SSM runtime base-url contract for deploy validation](../spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md)"
---

## Summary

Records a historical decision to source deploy-validation base URLs from
SSM-backed marker stacks. The active release workflow now accepts the runtime
base URL explicitly, and the authenticated AWS account audited for this branch
does not contain `/nova/*/base-url` parameters.

## Context

Pipeline validation quality depends on using correct environment URLs. Manual,
ad-hoc URL entry allows placeholder values and undermines gate evidence quality.

## Decision

1. Runtime validation base URLs were intended to be SSM-governed authority
   values.
2. Environment base URLs passed to CI/CD and validation workflows must be HTTPS
   and environment-scoped (`dev`/`prod`).
3. Release/runbook evidence must include provenance of base URL values used for
   validation gates.
4. Template and runbook contracts must stay synchronized for base URL sourcing.
5. Base-url parameters were single-owner resources managed only by the canonical
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
