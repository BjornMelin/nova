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
Installed-package typing metadata shipped by runtime distributions
`nova_file_api` and `nova_auth_api` is separate from the generated SDK trees
documented here.

Generator-facing OpenAPI rules that downstream consumers can rely on:

- stable snake_case `operationId` values for generated function names
- semantic tags for generated package/module grouping
- committed Python SDK trees regenerated from
  `../../packages/contracts/openapi/*.openapi.json`
