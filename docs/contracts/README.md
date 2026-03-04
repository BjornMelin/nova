# WS6/WS8 Contract Schemas

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-03

## Purpose

Provide machine-readable JSON schema contracts for reusable post-deploy
workflow APIs, downstream size profiles, and release artifacts used by WS6/WS8
release and consumer integration gates.

## Schema Set

- `reusable-workflow-inputs-v1.schema.json`
  - Defines typed v1 workflow input contracts for reusable deployment APIs.
- `reusable-workflow-outputs-v1.schema.json`
  - Defines typed v1 workflow output contracts for reusable deployment APIs.
- `deploy-size-profiles-v1.json`
  - Canonical profile presets and default ports for dash/rshiny/react-next.
- `release-artifacts-v1.schema.json`
  - Defines JSON artifact envelopes for release gates and post-deploy
    validation outputs.
- `workflow-post-deploy-validate.schema.json`
  - Workflow-specific validation schema for the reusable post-deploy contract.

## Related references

- `../clients/post-deploy-validation-integration-guide.md`
- `../plan/release/RELEASE-POLICY.md`
- `../architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`

## Versioning policy

- `v1` is the stable rolling compatibility channel.
- `v1.x.y` tags are immutable releases and are required for production pinning.
