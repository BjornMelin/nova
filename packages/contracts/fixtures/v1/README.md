# Nova Contract Fixtures v1

Canonical, versioned fixture bundle for cross-framework conformance on:

- Transfer initiate contract (`POST /v1/transfers/uploads/initiate`)
- Export workflow create/status contracts (`POST /v1/exports`, `GET /v1/exports/{export_id}`)
- v1 capability surface (`/v1/exports`, `/v1/exports/{export_id}`, `/v1/capabilities`, `/v1/resources/plan`, `/v1/releases/info`, `/v1/health/live`, `/v1/health/ready`)
- Canonical error envelope (`error.code`, `error.message`, `error.details`, `error.request_id`)

Route namespace policy:

- Canonical consumer route namespace is `/v1/*`.
- `/api/v1/*` namespace aliases are not part of the contract and are not
  accepted in fixtures/conformance references.
- Legacy `/api/*`, `/healthz`, and `/readyz` routes are removed and are not
  valid fixture references.

## Location and ownership

- Canonical root: `packages/contracts/fixtures/v1`
- Ownership: Nova architecture contract authority
- Versioning: add a sibling folder (`v2`, `v3`, ...) for breaking fixture/schema evolution

## Package contents

- `manifest.json` – stable index for machine consumers
- `schemas/*.schema.json` – JSON Schema draft 2020-12 files
- `fixtures/**` – canonical request/response JSON examples

## Consumer usage

### Dash/Python lanes

1. Load `manifest.json` to resolve schema + fixture paths.
2. Validate fixture JSON against schema files.
3. Validate decoded payloads using generated/python contract models.
4. Assert canonical error envelope parity for 503 fixtures.

### Shiny/R lanes

1. Read fixtures with `jsonlite::fromJSON`.
2. Validate top-level and required fields against schema-required keys.
3. Assert queue-unavailable error shape and file API response parity.
4. Keep adapter logic thin: no schema forks and no local authority mapping.

### TypeScript lanes

1. Import fixture JSON as test fixtures.
2. Exercise generated `@nova/sdk-file/client` methods against fixture-backed
   mock fetch implementations.
3. Assert runtime handling for:
   - `create.503.queue-unavailable`

## Governance requirements

- Do not overwrite existing `v1` fixture semantics.
- Additive changes are allowed when backward compatible.
- Breaking fixture/schema changes require new versioned folder and SemVer-major SDK release alignment (SPEC-0012).
