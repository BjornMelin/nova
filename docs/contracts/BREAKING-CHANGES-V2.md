# Breaking changes v2

> **Implementation state:** Approved hard-cut change record for the wave-2 program.

This file records the intentional hard cuts in the second green-field program.

## Public API

- Delete same-origin/session auth completely.
- Delete `X-Session-Id` and any body `session_id`.
- Delete `X-Scope-Id`.
- Delete any auth-service verification endpoints from the supported external surface.
- Delete legacy remote-auth mode settings and auth-service routing inputs.
- Delete generic job enqueue/read/update routes from the public surface.
- Replace generic jobs with explicit export workflow resources.

## Internal API

- Delete the internal worker callback route.
- Delete worker callback semantics.

## Runtime/infrastructure

- Delete Redis as a required runtime dependency.
- Delete `CACHE_REDIS_URL` and the `CACHE_REDIS_*` runtime/deploy surface.
- Delete `CACHE_SHARED_TTL_SECONDS`; distributed cache semantics are no longer part of the canonical runtime.
- Require `IDEMPOTENCY_DYNAMODB_TABLE` for API runtimes when idempotency is
  enabled.
- Require `IdempotencyTableName` and `FileTransferIdempotencyTableArn` in ECS/service deploy wiring.
- Treat `IDEMPOTENCY_DYNAMODB_TABLE` as stack-derived rather than operator-supplied JSON.
- Rename readiness diagnostic `shared_cache` to `idempotency_store`.
- Replace ECS/worker-first target architecture with HTTP API + Lambda + Step Functions as the canonical AWS deployment shape.
- Add `packages/nova_workflows` and `infra/nova_cdk` as first-class canonical platform components.

## SDK/package layout

- Delete auth SDK packages.
- Delete the dedicated auth service package family.
- Rename file-only SDK packages to unified Nova SDK package names.
- Rename the legacy file-only Python SDK package/import surface to
  `packages/nova_sdk_py` / `nova_sdk_py`.
- Rename the TypeScript package from `@nova/sdk-file` to `@nova/sdk`.
- Rename the legacy file-only R SDK package to `packages/nova_sdk_r` and `nova`,
  and rename the exported constructor/helper/wrapper surface to
  `create_nova_client`, `nova_bearer_token`, and `nova_<operation_id>`.
- Delete `@nova/sdk-fetch`.

## Docs/governance

- Archive or delete historical, non-canonical planning material from active authority.
