# Post-Deploy Validation Integration Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-09

## Purpose

Integrate downstream consumer repos with Nova post-deploy route validation
using the published reusable workflow contract and WS6/WS8 schemas.

## Inputs

- Reusable workflow reference:
  - quick start compatibility channel:
    `3M-Cloud/nova/.github/workflows/reusable-post-deploy-validate.yml@v1`
  - immutable production pin:
    `3M-Cloud/nova/.github/workflows/reusable-post-deploy-validate.yml@v1.x.y`
  - full commit SHA pin is also supported for maximum determinism
- Required repo variable in consumer repo: `NOVA_API_BASE_URL`
  - Must be an HTTPS base URL.
- Optional path overrides:
  - `validation_canonical_paths`
  - `validation_legacy_404_paths`

## Step-by-step commands

1. Copy one minimal workflow from `examples/workflows/` into your consumer
   repo.
2. Set `NOVA_API_BASE_URL` in repository variables.
3. For production or high-assurance automation, pin the workflow reference to
   an immutable `@v1.x.y` release tag or a full commit SHA before use.
4. Dispatch the workflow after deployment and review uploaded
   `post-deploy-validation-report` artifact.

## Acceptance checks

- Workflow calls
  `3M-Cloud/nova/.github/workflows/reusable-post-deploy-validate.yml`.
- Output `validation_status` is `passed`.
- Report JSON follows
  `docs/contracts/release-artifacts-v1.schema.json#/\$defs/post_deploy_validation_report`.
- Workflow input/output shape matches
  `docs/contracts/workflow-post-deploy-validate.schema.json`.
- Shared reusable deployment API contracts remain aligned with
  `docs/contracts/reusable-workflow-inputs-v1.schema.json` and
  `docs/contracts/reusable-workflow-outputs-v1.schema.json`.
- Browser live-gate artifacts (WS5) follow
  `docs/contracts/browser-live-validation-report.schema.json`.

## Usage notes

- `@v1` is the stable compatibility channel for onboarding and quick starts.
- Committed Nova consumer examples use immutable release tags (`@v1.x.y`) so
  the checked-in workflow ref is deterministic.
- Production and high-assurance consumers should pin `@v1.x.y` or a full
  commit SHA.
- Branch refs such as `@main` are not part of the supported consumer contract.

## References

- `docs/contracts/README.md`
- `docs/contracts/deploy-size-profiles-v1.json`
- `docs/contracts/workflow-auth0-tenant-deploy.schema.json`
- `docs/contracts/browser-live-validation-report.schema.json`
- GitHub reusable workflow docs:
  <https://docs.github.com/en/actions/using-workflows/reusing-workflows>
