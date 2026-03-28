# Workflow and release contract schemas

Status: Active
Current repository state: **pre-wave-2 implementation baseline**
Last reviewed: 2026-03-25

## Current machine-readable contract set

These schemas remain the current baseline contract artifacts until code changes
replace them:

- `reusable-workflow-inputs-v1.schema.json`
- `reusable-workflow-outputs-v1.schema.json`
- `deploy-size-profiles-v1.json`
- `release-artifacts-v1.schema.json`
- `workflow-post-deploy-validate.schema.json`
- `workflow-auth0-tenant-deploy.schema.json`
- `browser-live-validation-report.schema.json`
- `workflow-auth0-tenant-ops-v1.schema.json`
- `ssm-runtime-base-url-v1.schema.json`

## Approved breaking-change record for wave 2

- `BREAKING-CHANGES-V2.md`

That file is the authoritative human-readable ledger of the intentional hard
cuts planned for implementation.

## Rule

Keep current machine-readable schemas authoritative for the current baseline
until the implementation branches replace them. Do not treat the wave-2
breaking-change record as if it had already landed in the code.
