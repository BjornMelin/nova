# Workflow and Release Contract Schemas

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-24

## Purpose

Provide machine-readable JSON schema contracts for reusable workflows,
downstream size profiles, release artifacts, and deploy-validation records.

## Schema Set

- `reusable-workflow-inputs-v1.schema.json`
  - Defines typed v1 workflow input contracts for reusable deployment APIs.
- `reusable-workflow-outputs-v1.schema.json`
  - Defines workflow-specific output variants:
    - `#/$defs/cloudformation_change_set_output`
    - `#/$defs/codepipeline_execution_output`
    - `#/$defs/validation_report_output`
    - `#/$defs/manifest_output`
    - `#/$defs/deploy_runtime_output`
- `deploy-size-profiles-v1.json`
  - Canonical profile presets and default ports for dash/rshiny/react-next.
- `release-artifacts-v1.schema.json`
  - Defines JSON artifact envelopes for release gates and post-deploy
    validation outputs.
- `workflow-post-deploy-validate.schema.json`
  - Workflow-specific validation schema for the reusable post-deploy contract.
- `workflow-auth0-tenant-deploy.schema.json`
  - Workflow-specific validation schema for reusable Auth0 tenant ops API.
- `browser-live-validation-report.schema.json`
  - Browser/live validation gate artifact contract for dash-pca + Nova.
- `workflow-auth0-tenant-ops-v1.schema.json`
  - Workflow-specific contract schema for Auth0 tenant operation reusable APIs.
- `ssm-runtime-base-url-v1.schema.json`
  - SSM parameter path + HTTPS value contract for runtime deploy-validation base URLs.

## Related references

- `../standards/repository-engineering-standards.md`
- `../clients/post-deploy-validation-integration-guide.md`
- `../runbooks/release/release-policy.md`
- `../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `../architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`
- `../architecture/spec/SPEC-0000-http-api-contract.md`
- `../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `../architecture/spec/SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md`
- `../architecture/spec/SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md`
- `../architecture/spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md`
- `../architecture/requirements.md`

## Versioning policy

- `v1` is the stable rolling compatibility channel.
- `v1.x.y` tags are immutable releases and are required for production pinning.
