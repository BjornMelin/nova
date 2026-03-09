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

## Contract sources

- `../contracts/reusable-workflow-inputs-v1.schema.json`
- `../contracts/reusable-workflow-outputs-v1.schema.json#/$defs/validation_report_output`
- `../contracts/deploy-size-profiles-v1.json`
- `../contracts/release-artifacts-v1.schema.json`
