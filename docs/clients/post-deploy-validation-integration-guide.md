# Post-Deploy Validation Integration Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-03

## Purpose

Integrate downstream consumer repos with Nova post-deploy route validation
using the reusable workflow API and WS6/WS8 contract schemas.
This guide is designed as a 5-minute setup flow for downstream repos.

## Inputs

- Reusable workflow reference:
  `3M-Cloud/nova/.github/workflows/reusable-post-deploy-validate.yml@v1`
- Required repo variable in consumer repo: `NOVA_API_BASE_URL`
  - Must be an HTTPS base URL.
- Optional path overrides:
  - `validation_canonical_paths`
  - `validation_legacy_404_paths`

## Step-by-step commands

1. Copy one minimal workflow from `examples/workflows/` into your consumer
   repo.
2. Set `NOVA_API_BASE_URL` in repository variables.
3. Pin workflow reference to a release tag or commit SHA before production use.
   - Stable channel: `@v1`
   - Immutable pin: `@v1.x.y` (or commit SHA) for production pipelines
4. Dispatch the workflow after deployment and review uploaded
   `post-deploy-validation-report` artifact.

## Acceptance checks

- Workflow calls
  `3M-Cloud/nova/.github/workflows/reusable-post-deploy-validate.yml`.
- Output `validation_status` is `passed`.
- Report JSON follows
  `docs/contracts/release-artifacts-v1.schema.json#/$defs/post_deploy_validation_report`.
- Workflow input/output shape matches
  `docs/contracts/workflow-post-deploy-validate.schema.json`.
- Shared reusable deployment API contracts remain aligned with
  `docs/contracts/reusable-workflow-inputs-v1.schema.json` and
  `docs/contracts/reusable-workflow-outputs-v1.schema.json#/$defs/validation_report_output`.
- Browser live-gate artifacts (WS5) follow
  `docs/contracts/browser-live-validation-report.schema.json`.

## Versioning policy references

- `docs/runbooks/release/release-policy.md` (release branch, immutable artifact, and
  promotion policy)
- `docs/architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`
  (SemVer and compatibility governance)
- `docs/release/RELEASE-VERSION-MANIFEST.md` (release artifact evidence)
- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md` (route canonicalization authority)
- `docs/architecture/spec/SPEC-0000-http-api-contract.md` (baseline API authority)
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md` (v1 route namespace contract)
- `docs/architecture/requirements.md` (runtime and operational requirements baseline)

## References

- `docs/contracts/README.md`
- `docs/contracts/deploy-size-profiles-v1.json`
- `docs/contracts/workflow-auth0-tenant-deploy.schema.json`
- `docs/contracts/browser-live-validation-report.schema.json`
- GitHub reusable workflow docs:
  <https://docs.github.com/en/actions/using-workflows/reusing-workflows>
