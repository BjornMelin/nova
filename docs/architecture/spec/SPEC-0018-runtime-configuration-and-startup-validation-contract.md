---
Spec: 0018
Title: Runtime configuration and startup validation contract
Status: Active
Version: 2.6
Date: 2026-03-20
Related:
  - "[ADR-0026: Fail-fast runtime configuration and safe auth execution](../adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)"
  - "[SPEC-0017: Runtime component topology and ownership contract](./SPEC-0017-runtime-component-topology-and-ownership-contract.md)"
  - "[SPEC-0001: Security model](./SPEC-0001-security-model.md)"
---

## 1. Scope

Defines the runtime configuration source of truth, startup validation rules, and
readiness semantics for Nova runtime packages.

## 2. Configuration authority

1. `packages/nova_file_api/src/nova_file_api/config.py` is the typed
   environment contract for the file API runtime.
2. `packages/nova_dash_bridge/src/nova_dash_bridge/config.py` may define
   adapter-local environment settings only.
3. `scripts/release/runtime_config_contract.py` is the only allowed curated
   supplement for deploy-template metadata that cannot be inferred from
   `Settings` alone.
4. `scripts/release/generate_runtime_config_contract.py` must keep the
   committed runtime-config JSON and Markdown artifacts current.
5. Each externally configurable runtime setting must declare one explicit
   non-empty string `validation_alias`.
6. Release tooling derives env var names from `field.validation_alias` only and
   does not fall back to `alias` or `FIELD_NAME.upper()`.
7. Bridge code must not mutate `nova_file_api.Settings()` or recreate runtime
   authority through ambient settings rewriting.

## 3. Fail-fast startup rules

The process must fail before serving traffic when required backend couplings are
invalid.

Required startup validation:

1. `EXPORTS_ENABLED=true` requires `EXPORTS_DYNAMODB_TABLE`.
2. `EXPORTS_ENABLED=true` in the API Lambda requires
   `EXPORT_WORKFLOW_STATE_MACHINE_ARN`.
3. Workflow-task runtime startup also requires `EXPORTS_DYNAMODB_TABLE`; the
   shared workflow runtime does not fall back to `MemoryExportRepository()`
   when the exports table is blank.
4. DynamoDB-backed scoped export listing requires the exports table GSI
   `scope_id-created_at-index`; the runtime does not fall back to `Scan`.
5. `ACTIVITY_STORE_BACKEND=dynamodb` requires `ACTIVITY_ROLLUPS_TABLE`.
6. `IDEMPOTENCY_ENABLED` and `IDEMPOTENCY_TTL_SECONDS` are the current
   idempotency settings surface; the runtime does not define
   `IDEMPOTENCY_MODE`.
7. API-runtime `IDEMPOTENCY_ENABLED=true` requires
   `IDEMPOTENCY_DYNAMODB_TABLE` and DynamoDB-backed claim storage for
   duplicate prevention across instances.
8. Shared idempotency-store failures return `503` with
   `error.code = "idempotency_unavailable"`; mutation correctness does not
   fall back to local-only claim handling.
9. Deploy and operator docs must enforce the DynamoDB-table requirement without
   adding a mode matrix.
10. Runtime configuration aliases that duplicate canonical settings are
   deprecated and must be removed instead of carried forward.
11. Default runtime posture for file transfer MUST set:

    - `FILE_TRANSFER_MAX_UPLOAD_BYTES=536_870_912_000`
    - `FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS=1800`

12. Active operator docs and infra tests must consume the generated
    runtime-config contract artifacts instead of maintaining duplicate env-key
    lists by hand.

## 4. Readiness contract

1. `/v1/health/live` is process liveness only.
2. `/v1/health/ready` reports the current runtime dependency checks and
   returns `503` when any traffic-critical check is false.
3. Missing or blank `FILE_TRANSFER_BUCKET` fails readiness.
4. Incomplete in-process bearer-verifier configuration (`OIDC_ISSUER`,
   `OIDC_AUDIENCE`, or `OIDC_JWKS_URL` missing) fails the `auth_dependency`
   readiness check.
5. Runtime ECS/CloudFormation templates keep their default parameter sets
   validation-safe; incomplete bearer-verifier OIDC inputs are enforced by
   Nova readiness/startup behavior, not by template-parameter validation
   rules.
6. When exports are disabled, the reported `export_runtime` check remains ready
   instead of making the service unready by feature disablement alone.
7. `idempotency_store` health remains visible in diagnostics and gates
   readiness only when idempotency is enabled.
8. Activity-store health remains visible in diagnostics but is not
   readiness-fatal in the current contract.
9. Feature flags do not determine readiness by themselves.

## 5. Environment and startup ownership

1. Lifespan/startup bootstraps settings once per process and wires the runtime
   container from those validated settings.
2. Configuration errors must be explicit and actionable at startup.
3. Runtime docs and tests must treat startup validation as a contract, not as
   implementation detail.

## 6. Acceptance criteria

1. Runtime docs reference this spec for backend-coupling rules.
2. Active docs state the current shared-idempotency and scoped-readiness
   contract and do not claim an unimplemented `IDEMPOTENCY_MODE`.
3. Bridge and adapter docs do not claim separate runtime startup contracts.
4. Runtime deploy/docs/tests share a single generated env/override matrix.

## 7. Traceability

- [FR-0002](../requirements.md#fr-0002-operational-endpoints)
- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
- [NFR-0106](../requirements.md#nfr-0106-no-shim-posture)
