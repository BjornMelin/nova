# Post-Deploy Validation Integration Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-29

## Purpose

Integrate downstream consumer repos with Nova post-deploy runtime validation
using the reusable workflow API, the authoritative Nova deploy-output artifact,
and the active Nova contract schemas.
This guide is designed as a 5-minute setup flow for downstream repos.

## Inputs

- Reusable workflow reference:
  `3M-Cloud/nova/.github/workflows/reusable-post-deploy-validate.yml@<pin-to-an-immutable-revision>`
- Required runtime evidence from Nova:
  - `Deploy Runtime` workflow run id
  - `deploy-runtime-output` artifact produced by that run
- Optional path overrides:
  - `validation_canonical_paths`
  - `validation_legacy_404_paths`

## Step-by-step commands

1. Copy one minimal workflow from `examples/workflows/` into your consumer
   repo.
2. Trigger Nova `Deploy Runtime` and record its workflow run id.
3. Keep the reusable workflow pinned to an immutable revision for production
   use. Prefer a full commit SHA.
4. Dispatch the workflow with the Nova deploy run id and review uploaded
   `post-deploy-validation-report` artifact.

## Acceptance checks

- Workflow calls
  `3M-Cloud/nova/.github/workflows/reusable-post-deploy-validate.yml`.
- Output `validation_status` is `passed`.
- Validation resolves its target from the authoritative deploy-output artifact,
  not from a free-text URL string.
- Report JSON follows
  `docs/contracts/release-artifacts-v1.schema.json#/$defs/post_deploy_validation_report`.
- Workflow input/output shape matches
  `docs/contracts/workflow-post-deploy-validate.schema.json`.
- Deploy-output evidence follows
  `docs/contracts/deploy-output-authority-v2.schema.json`.
- Browser live-gate artifacts (WS5) follow
  `docs/contracts/browser-live-validation-report.schema.json`.

## Versioning policy references

- `docs/runbooks/release/release-policy.md` (release branch, immutable artifact, and
  promotion policy)
- `docs/architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`
  (SemVer and compatibility governance)
- `docs/release/RELEASE-VERSION-MANIFEST.md` (release artifact evidence)
- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md` (route canonicalization authority)
- `docs/architecture/spec/SPEC-0027-public-api-v2.md` (active API authority)
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md` (v1 route namespace contract)
- `docs/architecture/requirements-wave-2.md` (runtime and operational requirements baseline)

## References

- `docs/contracts/README.md`
- `docs/contracts/deploy-output-authority-v2.schema.json`
- `docs/contracts/workflow-deploy-runtime-v1.schema.json`
- `docs/contracts/browser-live-validation-report.schema.json`
- GitHub reusable workflow docs:
  <https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows>
