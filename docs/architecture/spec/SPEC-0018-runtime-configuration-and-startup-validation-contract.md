---
Spec: 0018
Title: Runtime configuration and startup validation contract
Status: Active
Version: 2.3
Date: 2026-03-11
Related:
  - "[ADR-0026: Fail-fast runtime configuration and safe auth execution](../adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)"
  - "[SPEC-0017: Runtime component topology and ownership contract](./SPEC-0017-runtime-component-topology-and-ownership-contract.md)"
  - "[SPEC-0001: Security model](./SPEC-0001-security-model.md)"
  - "[SPEC-0008: Async jobs and worker orchestration](./SPEC-0008-async-jobs-and-worker-orchestration.md)"
---

## 1. Scope

Defines the runtime configuration source of truth, startup validation rules, and
readiness semantics for Nova runtime packages.

## 2. Configuration authority

1. `packages/nova_file_api/src/nova_file_api/config.py` is the typed
   environment contract for the file API runtime.
2. `packages/nova_auth_api/src/nova_auth_api/config.py` is the typed
   environment contract for the auth API runtime.
3. `packages/nova_dash_bridge/src/nova_dash_bridge/config.py` may define
   adapter-local environment settings only.
4. Bridge code must not mutate `nova_file_api.Settings()` or recreate runtime
   authority through ambient settings rewriting.

## 3. Fail-fast startup rules

The process must fail before serving traffic when required backend couplings are
invalid.

Required startup validation:

1. `JOBS_QUEUE_BACKEND=sqs` with `JOBS_ENABLED=true` requires
   `JOBS_SQS_QUEUE_URL`.
2. `JOBS_REPOSITORY_BACKEND=dynamodb` requires `JOBS_DYNAMODB_TABLE`.
3. DynamoDB-backed scoped job listing requires the jobs table GSI
   `scope_id-created_at-index`; the runtime does not fall back to `Scan`.
4. `JOBS_RUNTIME_MODE=worker` requires:
   - `JOBS_ENABLED=true`
   - `JOBS_QUEUE_BACKEND=sqs`
   - `JOBS_SQS_QUEUE_URL`
   - `JOBS_API_BASE_URL`
   - `JOBS_WORKER_UPDATE_TOKEN`
   - deployment wiring that always injects `JOBS_WORKER_UPDATE_TOKEN`,
     including scale-from-zero ECS worker services
   - worker deployments MUST inject `JOBS_WORKER_UPDATE_TOKEN` from a
     secret-backed deployment input even when the ECS service is configured to
     start at zero tasks
   - release operator input for this worker secret MUST be
     `JOBS_WORKER_UPDATE_TOKEN_SECRET_ARN`
5. `ACTIVITY_STORE_BACKEND=dynamodb` requires `ACTIVITY_ROLLUPS_TABLE`.
6. `IDEMPOTENCY_ENABLED` and `IDEMPOTENCY_TTL_SECONDS` are the current
   idempotency settings surface; the runtime does not yet define
   `IDEMPOTENCY_MODE`.
7. `CACHE_REDIS_URL` enables the shared cache tier for duplicate prevention.
   Shared-cache failures degrade duplicate-claim handling to best-effort local
   behavior, and readiness reporting remains authoritative for deployment
   traffic policy.
8. Deploy and operator docs must not claim `IDEMPOTENCY_MODE` support until
   the runtime implements those semantics.
9. Runtime configuration aliases that duplicate canonical settings are
   deprecated and must be removed instead of carried forward.
10. Default runtime posture for file transfer MUST set:
   - `FILE_TRANSFER_MAX_UPLOAD_BYTES=536_870_912_000`
   - `FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS=1800`

## 4. Readiness contract

1. `/v1/health/live` is process liveness only.
2. `/v1/health/ready` reports the current runtime dependency checks and
   returns `503` when any reported check is false.
3. Missing or blank `FILE_TRANSFER_BUCKET` fails readiness.
4. `AUTH_MODE=jwt_local` with incomplete local verifier configuration
   (`OIDC_ISSUER`, `OIDC_AUDIENCE`, or `OIDC_JWKS_URL` missing) fails the
   `auth_dependency` readiness check.
5. When jobs are disabled, the reported `job_queue` check remains ready instead
   of making the service unready by feature disablement alone.
6. Shared cache and activity-store health remain visible in diagnostics and
   currently participate in overall readiness; shared-cache failures still
   degrade duplicate-claim handling to best-effort local behavior.
7. Feature flags do not determine readiness by themselves.

## 5. Environment and startup ownership

1. Lifespan/startup bootstraps settings once per process and wires the runtime
   container from those validated settings.
2. Configuration errors must be explicit and actionable at startup.
3. Runtime docs and tests must treat startup validation as a contract, not as
   implementation detail.

## 6. Acceptance criteria

1. Runtime docs reference this spec for backend-coupling rules.
2. Active docs state the current aggregate readiness contract and do not claim
   an unimplemented `IDEMPOTENCY_MODE`.
3. Bridge and adapter docs do not claim separate runtime startup contracts.

## 7. Traceability

- [FR-0002](../requirements.md#fr-0002-operational-endpoints)
- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
- [NFR-0106](../requirements.md#nfr-0106-no-shim-posture)
