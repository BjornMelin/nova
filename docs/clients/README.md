# Downstream Consumer Docs

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-03

## Purpose

Provide minimal downstream integration artifacts for Dash, R Shiny, and
React/Next consumers that call Nova reusable deployment and post-deploy
validation contracts.

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

Canonical documentation authority chain for this client surface:
[ADR-0023](../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md),
[SPEC-0000](../architecture/spec/SPEC-0000-http-api-contract.md),
[SPEC-0016](../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md),
[requirements.md](../architecture/requirements.md).

- `../contracts/reusable-workflow-inputs-v1.schema.json`
- `../contracts/reusable-workflow-outputs-v1.schema.json#/$defs/validation_report_output`
- `../contracts/deploy-size-profiles-v1.json`
- `../contracts/release-artifacts-v1.schema.json`
