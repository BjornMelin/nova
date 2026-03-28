# Workflow and release contract schemas

Status: Active
Current repository state: **canonical wave-2 serverless baseline**
Last reviewed: 2026-03-25

## Current machine-readable contract set

These schemas remain the current machine-readable baseline contract artifacts:

- `release-artifacts-v1.schema.json`
- `workflow-post-deploy-validate.schema.json`
- `workflow-auth0-tenant-deploy.schema.json`
- `browser-live-validation-report.schema.json`
- `workflow-auth0-tenant-ops-v1.schema.json`

## Approved breaking-change record for wave 2

- `BREAKING-CHANGES-V2.md`

That file remains the authoritative human-readable ledger of the intentional
hard cuts and already-landed contract changes across the wave-2 program.

## Rule

Keep only schemas that describe surviving release, validation, and Auth0
automation surfaces. Do not retain machine-readable contracts for deleted
deploy-runtime or release-control-plane paths.
