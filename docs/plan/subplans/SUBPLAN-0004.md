# SUBPLAN-0004

- Branch name: `feat/subplan-0004-e2e-validation-release-closure`

## E2E Validation + Release Closure

Order: 4 of 5
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

- `apps/nova_file_api_service`
- `apps/nova_auth_api_service`
- `packages/nova_file_api`
- `packages/nova_auth_api`
- `packages/nova_dash_bridge`
- `packages/contracts`
- `~/repos/work/infra-stack/container-craft`
- `~/repos/work/pca-analysis-dash/dash-pca`

## Checklist

### A. Contract and API readiness

- [x] Validate OpenAPI generation and contract diff checks
- [x] Validate error envelope/request-id behavior across major failure modes

### B. Security and auth readiness

- [x] Validate JWT failure mappings (issuer/audience/expiry/scope)
- [x] Validate remote auth mode fail-closed behavior
- [x] Validate no sensitive URL/token logging in synthetic tests

### C. Async and cache readiness

- [x] Validate enqueue -> worker -> completion path
- [x] Validate queue pressure and retry behavior
- [x] Validate enqueue publish-failure path returns `503 queue_unavailable`
- [x] Validate failed enqueue responses are not idempotency replay cached
- [x] Validate Redis failure fallback and idempotency replay behavior

### D. Observability and operations

- [ ] Validate dashboard population in non-prod
- [ ] Validate alarms trigger under controlled fault injection
- [x] Validate `/healthz` and `/readyz` operational behavior
- [x] Validate readiness remains `ok=true` when optional features are disabled

### E. Release closure

- [x] Update changelog/release notes and migration guidance
- [x] Close PLAN and subplan checklist statuses with evidence

## Acceptance Criteria

- End-to-end release checklist is complete.
- Evidence exists for all major runtime and infra gates.
- Remaining known risks are documented and accepted.

External AWS gate execution path:

- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
