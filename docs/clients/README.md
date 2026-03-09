# Integration Workflow Docs

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-09

## Purpose

Provide minimal downstream integration artifacts for Dash, R Shiny, and
React/Next consumers that call Nova reusable deployment and post-deploy
validation contracts. These docs are active authority for Nova's published
reusable-workflow integration surface.

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

Committed public client SDK trees in-repo today:

- `../../packages/nova_sdk_py_file/`
- `../../packages/nova_sdk_py_auth/`
- `../../packages/nova_dash_bridge/`

Retained TypeScript/R scaffolding and shared generator/runtime layers:

- `../../packages/nova_sdk_file_core/`
- `../../packages/nova_sdk_auth_core/`
- `../../packages/nova_sdk_fetch/`
- `../../packages/nova_sdk_r_file/`
- `../../packages/nova_sdk_r_auth/`

All of these remain subordinate to the committed Nova OpenAPI contracts. Public
SDK productization in this wave remains Python-only. The TypeScript/R packages
above remain internal/generated foundations and must not be deleted before a
later promotion wave lands. Internal-only operations stay in canonical OpenAPI
but are excluded from client SDK generation. Installed-package typing metadata
shipped by runtime distributions `nova_file_api` and `nova_auth_api` is
separate from the generated SDK trees documented here.

Generator-facing OpenAPI rules that downstream consumers can rely on:

- stable snake_case `operationId` values for generated function names
- semantic tags for generated package/module grouping
- committed Python SDK trees regenerated from
  `../../packages/contracts/openapi/*.openapi.json`

## Workflow reference policy

- `@v1` is the public compatibility channel for reusable workflow consumers.
- Committed downstream workflow examples pin immutable release tags such as
  `@v1.x.y`.
- Production and high-assurance consumers should pin `@v1.x.y` or a full
  commit SHA.
- Branch refs such as `@main` are not part of the supported consumer contract.
