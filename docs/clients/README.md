# Downstream Consumer Docs

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-24

## Purpose

Provide minimal downstream integration artifacts for Dash, R Shiny, and
React/Next consumers that call Nova reusable deployment and post-deploy
validation contracts. These docs are workflow/integration authority, not public
SDK release authority. Keep this file secondary to the active architecture and
release-policy docs.

For SDK governance and repo engineering standards, use:

- `../standards/README.md`
- `../architecture/spec/SPEC-0029-sdk-architecture-and-artifact-contract.md`
- `../architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`

## Contents

- `post-deploy-validation-integration-guide.md`
- `dash-minimal-workflow.yml`
- `rshiny-minimal-workflow.yml`
- `react-next-minimal-workflow.yml`
- `examples/workflows/dash-post-deploy-validate.yml`
- `examples/workflows/rshiny-post-deploy-validate.yml`
- `examples/workflows/react-next-post-deploy-validate.yml`

## Production-safe pinning

Use immutable refs so downstream deploy validation always runs the reviewed
workflow version. Use a full commit SHA (preferred) or a fully qualified
immutable tag.

- `dash-minimal-workflow.yml`: `uses: 3M-Cloud/nova/.github/workflows/reusable-post-deploy-validate.yml@655ccab0d071c828045de4a4d3bb441d4349194e`
- `rshiny-minimal-workflow.yml`: `uses: 3M-Cloud/nova/.github/workflows/reusable-post-deploy-validate.yml@655ccab0d071c828045de4a4d3bb441d4349194e`
- `react-next-minimal-workflow.yml`: `uses: 3M-Cloud/nova/.github/workflows/reusable-post-deploy-validate.yml@655ccab0d071c828045de4a4d3bb441d4349194e`
- `examples/workflows/dash-post-deploy-validate.yml`: `uses: 3M-Cloud/nova/.github/workflows/reusable-post-deploy-validate.yml@655ccab0d071c828045de4a4d3bb441d4349194e`
- `examples/workflows/rshiny-post-deploy-validate.yml`: `uses: 3M-Cloud/nova/.github/workflows/reusable-post-deploy-validate.yml@655ccab0d071c828045de4a4d3bb441d4349194e`
- `examples/workflows/react-next-post-deploy-validate.yml`: `uses: 3M-Cloud/nova/.github/workflows/reusable-post-deploy-validate.yml@655ccab0d071c828045de4a4d3bb441d4349194e`

When migrating a pinned reference, validate compatibility with
`reusable-workflow-inputs-v1.schema.json` and
`reusable-workflow-outputs-v1.schema.json` in this repository’s `contracts`
directory, then verify downstream consumers against
`release-artifacts-v1.schema.json` and `deploy-size-profiles-v1.json`.

## Contract sources

- `../contracts/reusable-workflow-inputs-v1.schema.json`
- `../contracts/reusable-workflow-outputs-v1.schema.json`
- `../contracts/deploy-size-profiles-v1.json`
- `../contracts/release-artifacts-v1.schema.json`
- `../../packages/contracts/openapi/nova-file-api.openapi.json`

## SDK package status

Release-grade public SDK packages for this wave:

- `../../packages/nova_sdk_py_file/`

Integration adapter packages retained in-repo for downstream framework wiring:

- `../../packages/nova_dash_bridge/`

TypeScript SDK package retained in-repo as a release-grade CodeArtifact
staged/prod artifact:

- `../../packages/nova_sdk_file/`

R SDK packages retained in-repo as first-class internal release artifacts:

- `../../packages/nova_sdk_r_file/`

Downstream R and Shiny consumers should treat `nova.sdk.r.file` as the only
canonical Nova HTTP client surface in this wave. Use
`create_nova_file_client(base_url, bearer_token = NULL, bearer_token_env =
"NOVA_FILE_BEARER_TOKEN", ...)` plus the generated
`nova_file_<operation_id>()` wrappers. App-specific convenience helpers belong
in consumer repos; they must not recreate a second SDK or a retired auth-verify
contract.

`nova_dash_bridge` is an adapter-only package, not release-grade SDK contract
authority. It consumes the canonical in-process bridge seam exposed by
`nova_file_api.public`. FastAPI hosts use that async-first seam directly,
while Flask/Dash retain the explicit thin sync adapter only at the sync edge.

Dash and other browser-backed consumers using `nova_dash_bridge` must expose a
bearer `Authorization` header to the bridge assets for canonical
`/v1/transfers` and `/v1/jobs` requests. Active consumer docs must not describe
`session_id`, `X-Session-Id`, or `X-Scope-Id` as public auth/scope inputs.

All of these remain subordinate to the committed Nova OpenAPI contracts.
TypeScript SDK package is release-grade within Nova's CodeArtifact
staged/prod flow, remain subpath-only, and do not ship bundled runtime
validation. R packages are built as real packages, transported through
CodeArtifact generic packages, and evidenced with signed tarballs rather than a
separate public registry.

For the current file API contract, the R package is intentionally JSON-only and
uses concrete path/query parameters in generated wrappers instead of public
`path_params`, `query`, or `content_type` bags. Optional per-request headers
remain available through `headers` / `default_headers`.

Generator-facing OpenAPI rules that downstream consumers can rely on:

- stable, explicit snake_case `operationId` values for generated function
  names
- semantic tags for generated package/module grouping
- committed Python SDK artifacts and release-grade TypeScript SDK artifacts
  regenerated from `../../packages/contracts/openapi/*.openapi.json`
- committed Python SDK module sources generated by
  `scripts/release/generate_python_clients.py` using the pinned
  `openapi-python-client==0.28.3` toolchain and committed assets under
  `../../scripts/release/openapi_python_client/`
- release-grade TypeScript SDK `types` subpaths expose curated public
  operation helpers and reachable public schema aliases only
- R package release artifacts are built from the same OpenAPI sources and
  preserved as signed tarball evidence in release runs

## R Shiny consumer baseline

- Authenticate to Nova with bearer JWT only.
- Do not call or document `nova-auth-api`, `/v1/token/verify`, or
  `/v1/token/introspect`.
- Fail closed on missing `NOVA_API_BASE_URL` / `NOVA_FILE_BEARER_TOKEN` in the
  consumer repo's real bootstrap path.
- Keep consumer-side wrappers thin and app-owned; Nova remains the HTTP client
  and contract authority.
