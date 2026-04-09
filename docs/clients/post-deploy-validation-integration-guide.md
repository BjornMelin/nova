# Post-Deploy Validation Integration Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-04-04

## Purpose

Integrate downstream consumer repos with Nova post-deploy runtime validation
using the reusable workflow API, the authoritative Nova deploy-output artifact,
and the active Nova contract schemas.
This guide is designed as a 5-minute setup flow for downstream repos.

## Inputs

- Reusable workflow reference:
  `REPLACE_WITH_NOVA_REPO/.github/workflows/reusable-post-deploy-validate.yml@<pin-to-an-immutable-revision>`
- Required runtime evidence from Nova:
  - `deploy-output.json`
  - `deploy-output.sha256` when you want digest verification inside the workflow
- Optional path overrides:
  - `validation_canonical_paths`
  - `validation_protected_paths`
  - `validation_legacy_404_paths`
  - `validation_cors_preflight_path`
  - `validation_cors_origin` when you need to override the origin derived from
    `deploy-output.json`
- Optional AWS runtime validation input:
  - `aws_role_to_assume` when the calling repo has an approved read-only role
    for the deployed Nova account
  - the caller workflow must also allow `id-token: write`, and the role trust
    policy must accept the caller repository via GitHub OIDC

## Step-by-step commands

1. Copy one minimal workflow from `examples/workflows/` into your consumer
   repo.
2. Make the authoritative Nova `deploy-output.json` available to the consumer
   workflow as one of:
   - a checked-in file path
   - a prior downloaded artifact path
   - a repository or environment variable passed as `deploy_output_json`
   Use `deploy_output_path` when your consumer workflow already has the file on
   disk and use `deploy_output_json` when you want to pass the payload directly.
3. Keep the reusable workflow pinned to an immutable revision for production
   use. Prefer a full commit SHA.
4. Dispatch the workflow with the deploy-output input and review the uploaded
   `post-deploy-validation-report` artifact.
5. Set `aws_role_to_assume` only when you want the reusable workflow to check
   live AWS runtime state in addition to the public HTTPS contract.

## Acceptance checks

- Workflow calls
  `REPLACE_WITH_NOVA_REPO/.github/workflows/reusable-post-deploy-validate.yml`.
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
- `/v1/health/ready` now reflects the full live traffic readiness surface
  below the route boundary, including transfer and auth checks plus
  diagnostic-only export/idempotency/activity probes, not configuration
  presence alone.
- At least one protected route returns `401` or `403` without a bearer token.
- `GET /v1/capabilities/transfers` returns the effective transfer envelope and
  the representative upload sizing checks pass in the report.
- Browser CORS preflight on the protected export route returns the expected
  allow-origin, allow-methods, and allow-headers contract.
- When `aws_role_to_assume` is configured:
  - reserved concurrency matches the deploy environment policy for the API
    Lambda and workflow task Lambdas
  - runtime CloudWatch alarms are not in `ALARM`
  - the exported observability dashboard exists
  - the latest transfer-policy AppConfig deployment is complete
  - the transfer spend budget includes at least one `ACTUAL` notification
- Browser live validation remains a separate operator/browser workflow. Use
  `docs/runbooks/release/browser-live-validation-checklist.md` when you need
  deployed browser evidence and the WS5 artifact set.

## Versioning policy references

- `docs/runbooks/release/release-policy.md` (release branch, immutable artifact, and
  promotion policy)
- `docs/architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`
  (SemVer and compatibility governance)
- `release/RELEASE-VERSION-MANIFEST.md` (release artifact evidence)
- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md` (runtime authority)
- `docs/architecture/adr/ADR-0038-docs-authority-reset.md` (docs/router authority)
- `docs/architecture/spec/SPEC-0027-public-api-v2.md` (active API authority)
- `docs/architecture/spec/SPEC-0029-platform-serverless.md` (runtime/deploy authority)

## References

- `docs/contracts/README.md`
- `docs/contracts/deploy-output-authority-v2.schema.json`
- `docs/contracts/workflow-post-deploy-validate.schema.json`
- `docs/contracts/browser-live-validation-report.schema.json`
- `docs/contracts/release-artifacts-v1.schema.json`
- GitHub reusable workflow docs:
  <https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows>
