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
  - `validation_protected_paths`
  - `validation_legacy_404_paths`
  - `validation_cors_preflight_path`
  - `validation_cors_origin` when you need to override the origin derived from
    `deploy-output.json`

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
- Validation uses `deploy-output.json` as the runtime authority for
  `public_base_url`; downstream repos should not treat a manually configured
  `NOVA_API_BASE_URL` as the source of truth when deploy-output evidence is
  available.
- `deploy-output.json` binds the canonical public base URL, release version,
  release commit provenance, disabled execute-api endpoint, browser CORS
  authority, and stack-owned runtime outputs into one artifact.
- Report JSON follows
  `docs/contracts/release-artifacts-v1.schema.json#/$defs/post_deploy_validation_report`.
- Workflow input/output shape matches
  `docs/contracts/workflow-post-deploy-validate.schema.json`.
- Deploy-output evidence follows
  `docs/contracts/deploy-output-authority-v2.schema.json`.
- `/v1/releases/info` matches the deployed runtime version and environment from
  `deploy-output.json`.
- The disabled `execute-api` endpoint returns `403`, proving the custom domain
  is the only intended public ingress.
- `/v1/health/live` and `/v1/health/ready` return `200`.
- At least one protected route returns `401` or `403` without a bearer token.
- Reserved concurrency matches the deploy environment policy for the API Lambda
  and workflow task Lambdas.
- Browser CORS preflight on the protected export route returns the expected
  allow-origin, allow-methods, and allow-headers contract.
- Browser live-gate artifacts (WS5) follow
  `docs/contracts/browser-live-validation-report.schema.json`.

## Versioning policy references

- `docs/runbooks/release/release-policy.md` (release branch, immutable artifact, and
  promotion policy)
- `docs/architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`
  (SemVer and compatibility governance)
- `docs/release/RELEASE-VERSION-MANIFEST.md` (release artifact evidence)
- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md` (runtime authority)
- `docs/architecture/adr/ADR-0038-docs-authority-reset.md` (docs/router authority)
- `docs/architecture/spec/SPEC-0027-public-api-v2.md` (active API authority)
- `docs/architecture/spec/SPEC-0029-platform-serverless.md` (runtime/deploy authority)

## References

- `docs/contracts/README.md`
- `docs/contracts/deploy-output-authority-v2.schema.json`
- `docs/contracts/workflow-deploy-runtime-v1.schema.json`
- `docs/contracts/workflow-post-deploy-validate.schema.json`
- `docs/contracts/browser-live-validation-report.schema.json`
- `docs/contracts/release-artifacts-v1.schema.json`
- GitHub reusable workflow docs:
  <https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows>
