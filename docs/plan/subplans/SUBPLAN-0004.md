# SUBPLAN-0004

- Branch name: `feat/subplan-0004-e2e-validation-release-closure`

## E2E Validation + Release Closure

Order: 4 of 4
Parent plan: `docs/plan/PLAN.md`
Depends on: `SUBPLAN-0001`, `SUBPLAN-0002`, `SUBPLAN-0003`

## Persona

Release Architect (quality gates, rollout safety, operational readiness)

## Objective

Close the initial release with evidence-backed validation across contract,
security, async behavior, caching resilience, observability, and deployment
readiness.

## Scope

Repositories:

- `~/repos/work/infra-stack/aws-file-transfer-api`
- `~/repos/work/infra-stack/container-craft`
- `~/repos/work/infra-stack/aws-dash-s3-file-handler`
- `~/repos/work/pca-analysis-dash/dash-pca`

## Checklist

### A. Contract and API readiness

- [ ] Validate OpenAPI generation and contract diff checks
- [ ] Validate error envelope/request-id behavior across major failure modes

### B. Security and auth readiness

- [ ] Validate JWT failure mappings (issuer/audience/expiry/scope)
- [ ] Validate remote auth mode fail-closed behavior
- [ ] Validate no sensitive URL/token logging in synthetic tests

### C. Async and cache readiness

- [ ] Validate enqueue -> worker -> completion path
- [ ] Validate queue pressure and retry behavior
- [ ] Validate enqueue publish-failure path returns `503 queue_unavailable`
- [ ] Validate failed enqueue responses are not idempotency replay cached
- [ ] Validate Redis failure fallback and idempotency replay behavior

### D. Observability and operations

- [ ] Validate dashboard population in non-prod
- [ ] Validate alarms trigger under controlled fault injection
- [ ] Validate `/healthz` and `/readyz` operational behavior
- [ ] Validate readiness remains `ok=true` when optional features are disabled

### E. Release closure

- [ ] Update changelog/release notes and migration guidance
- [ ] Close PLAN and subplan checklist statuses with evidence

## Acceptance Criteria

- End-to-end release checklist is complete.
- Evidence exists for all major runtime and infra gates.
- Remaining known risks are documented and accepted.
