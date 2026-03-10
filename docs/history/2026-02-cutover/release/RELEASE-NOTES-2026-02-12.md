# Release Notes: 2026-02-12

Status: Finalized (pending live AWS validation gates)
Scope: `nova` runtime monorepo + cross-repo integration alignment

## Highlights

- Finalized monorepo runtime structure:
  - `packages/nova_file_api`
  - `packages/nova_auth_api`
  - `packages/nova_file_api`
  - `packages/nova_auth_api`
  - `packages/nova_dash_bridge`
  - `packages/contracts`
- Completed endpoint hard-cutover to:
  - `/api/transfers/*`
  - `/api/jobs/*`
- Finalized auth hardening:
  - local JWT verification via `oidc-jwt-verifier`
  - async threadpool boundary for sync verification
  - optional remote auth mode fail-closed behavior
- Finalized async jobs behavior:
  - enqueue publish failures surface as `503 queue_unavailable`
  - failed enqueue responses are not success replay cached by idempotency
  - worker result-update transitions enforce legal status rules (`409` on
    invalid transitions)
- Finalized observability behavior:
  - queue lag metric (`jobs_queue_lag_ms`)
  - worker update throughput counters
  - EMF payload and bounded-dimension validation
- Finalized bridge/runtime split:
  - `nova_dash_bridge.FileTransferService` delegates transfer control-plane
    operations to `nova_file_api.TransferService`
  - bridge keeps Dash/Flask/FastAPI adapters and app-facing helpers
- Added generated-client contract smoke:
  - OpenAPI -> `openapi-python-client` generation -> compile verification

## Compatibility and Breaking Changes

- Legacy path prefix `/api/file-transfer/*` is removed.
- Canonical runtime package namespace is `nova_file_api`.
- Bridge package namespace is `nova_dash_bridge`.

## Quality Gate Evidence

- Runtime monorepo:
  - `ruff`/`mypy`/`pytest` all passing (`49` tests)
  - generated-client smoke passing (`1` test)
- `container-craft`:
  - `ruff`/`mypy`/`pytest` all passing (`48` tests)
- `dash-pca`:
  - `ruff`/`pyright`/`pytest` all passing (`353` passed, `1` skipped)

## Remaining Release-Blocking Live Gates

- Validate sidecar ALB routing + health-check behavior in non-prod AWS.
- Validate non-prod end-to-end path:
  browser upload -> enqueue -> worker result -> download.
- Validate dashboard population and alarm trigger behavior via synthetic faults.

## Post-Release Fixes (2026-02-13)

- Fixed same-origin async polling scope propagation in bridge uploader:
  `GET /api/jobs/{job_id}` polling now includes `X-Session-Id`.
- Fixed EMF log shape to emit `_aws` + metric keys as top-level structured log
  fields instead of nested JSON strings.
- Added regression coverage for same-origin status auth semantics, bridge asset
  poll-header contract, and structured EMF payload assertions.

## Post-Release Fixes (2026-02-23)

- Fixed workspace packaging metadata to use in-project `README.md` files across
  all runtime packages/apps, restoring isolated `uv build` support.
- Fixed worker result normalization so `status=succeeded` always clears
  `error` state, including updates that provide a result payload.
- Fixed readiness bucket check semantics:
  - `FILE_TRANSFER_BUCKET` default is blank
  - `/readyz` treats blank/whitespace bucket values as unconfigured.
- Added regression coverage for:
  - succeeded updates clearing stale error values
  - readiness failing when bucket configuration is missing.
- Verification evidence:
  - runtime tests: `81 passed`
  - generated-client smoke: `1 passed`
  - workspace package/app builds: all five `uv build` runs passed.

Execution runbook for remaining live gates:

- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
