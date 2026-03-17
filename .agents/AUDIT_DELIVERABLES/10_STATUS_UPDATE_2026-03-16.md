# Audit status update (2026-03-16)

This note supersedes the repo-state portions of the original audit deliverables
for `NOVA-AUDIT-003` and `NOVA-AUDIT-004`.

Implementation branch: `fix/strict-shared-idempotency`

## Resolved in this branch

- `NOVA-AUDIT-003`
  Idempotent mutation entrypoints now require shared Redis claim storage when
  `IDEMPOTENCY_ENABLED=true`. Shared-store failures return `503` with
  `error.code = "idempotency_unavailable"` instead of falling back to local
  claim handling. Startup validation now rejects enabled idempotency without
  `CACHE_REDIS_URL`, and deploy automation/template rules enforce the same
  contract.
- `NOVA-AUDIT-004`
  `/v1/health/ready` now gates only traffic-critical dependencies derived from
  active runtime settings. `shared_cache` gates readiness only when
  idempotency is enabled, while `activity_store` remains visible as a
  diagnostic check without forcing readiness failure.

## Verification completed

- Targeted runtime tests cover:
  - shared-store outage on idempotency claim
  - shared-store outage on post-execute response persistence
  - shared-store duplicate-claim protection across store instances
  - readiness behavior with idempotency enabled/disabled
  - readiness behavior with activity-store degradation
  - startup validation for `IDEMPOTENCY_ENABLED=true` without cache wiring
- Infra contract tests cover:
  - ECS service-template rule requiring cache wiring when idempotency is
    enabled
  - deploy script rejection of `IDEMPOTENCY_ENABLED=true` with
    `FILE_TRANSFER_CACHE_ENABLED!=true`

## Current top remaining priority

- `NOVA-AUDIT-005`
  ECS IAM and secret-surface hardening is now the highest-priority remaining
  production-readiness item on current `main`.

## Historical context

- `09_STATUS_UPDATE_2026-03-14.md` remains accurate for the bridge/runtime
  authority reconciliation performed in PR #53.
- `02_REPOSITORY_AUDIT_REPORT.md`, `06_DOCS_AND_CONFIG_DRIFT_AUDIT.md`, and
  the original finding narratives remain historical evidence of the pre-fix
  repo state and should not be rewritten to appear current.
