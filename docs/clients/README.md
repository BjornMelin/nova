# Downstream Consumer Docs

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-05

## Purpose

Provide minimal downstream integration artifacts for Dash, R Shiny, and
React/Next consumers that call Nova reusable deployment and post-deploy
validation contracts. These docs are workflow/integration authority, not public
SDK release authority.

## Contents

- `post-deploy-validation-integration-guide.md`
- `dash-minimal-workflow.yml`
- `rshiny-minimal-workflow.yml`
- `react-next-minimal-workflow.yml`
- `examples/workflows/dash-post-deploy-validate.yml`
- `examples/workflows/rshiny-post-deploy-validate.yml`
- `examples/workflows/react-next-post-deploy-validate.yml`

## Production-safe pinning

The example workflows above currently show mutable refs (for example `@v1`) in places.
For release pipelines, prefer immutable refs so downstream deploy validation always
runs the reviewed workflow version. Use a full commit SHA (preferred) or a fully
qualified immutable tag.

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
- `../../packages/contracts/openapi/nova-auth-api.openapi.json`

## SDK package status

Public release-grade SDK packages for this wave:

- `../../packages/nova_sdk_py_file/`
- `../../packages/nova_sdk_py_auth/`
- `../../packages/nova_dash_bridge/`

Internal/generated catalogs retained in-repo for drift checks and deferred
productization:

- `../../packages/nova_sdk_file_core/`
- `../../packages/nova_sdk_auth_core/`
- `../../packages/nova_sdk_fetch/`
- `../../packages/nova_sdk_r_file/`
- `../../packages/nova_sdk_r_auth/`

All of these remain subordinate to the committed Nova OpenAPI contracts. Only
the Python packages above are public release-grade SDK authority in this wave.

Generator-facing OpenAPI rules that downstream consumers can rely on:

- stable snake_case `operationId` values for generated function names
- semantic tags for generated package/module grouping
- committed Python SDK trees regenerated from
  `../../packages/contracts/openapi/*.openapi.json`
