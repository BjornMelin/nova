# Workflow and release contract schemas

Status: Active
Current repository state: **canonical wave-2 serverless baseline**
Last reviewed: 2026-03-25

## Current machine-readable contract set

These schemas remain the current machine-readable baseline contract artifacts:

- `release-artifacts-v1.schema.json`
- `deploy-output-authority-v2.schema.json` (published runtime provenance and
  canonical public base URL authority)
- `release-prep-v1.schema.json`
- `release-execution-manifest-v1.schema.json`
- `workflow-post-deploy-validate.schema.json`
- `workflow-auth0-tenant-deploy.schema.json`
- `browser-live-validation-report.schema.json`
- `workflow-auth0-tenant-ops-v1.schema.json`

## Approved breaking-change record for wave 2

- `BREAKING-CHANGES-V2.md`

That file remains the authoritative human-readable ledger of the intentional
hard cuts and already-landed contract changes across the wave-2 program.

## Rule

Keep only schemas that describe surviving release, AWS-native post-merge
control-plane, release-prep metadata, release execution manifests, runtime
deploy provenance, validation, and Auth0 automation surfaces. Do not retain
machine-readable contracts for deleted GitHub release executors or any workflow
that writes release commits back to protected Git branches.
Do not treat execute-api hostnames as public runtime authority. When an
execute-api endpoint appears in deploy-output, it exists only to prove that the
default endpoint is blocked.
