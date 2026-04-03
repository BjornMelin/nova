# Client and downstream integration docs

Status: Active
Current repository state: **canonical wave-2 serverless baseline**
Last reviewed: 2026-04-02

## Start here

- Browser or Dash teams should begin with `browser-dash-integration-guide.md`.
  It is the primary onboarding path from Nova deploy output to a working
  uploader integration.
- SDK package selection starts with `CLIENT-SDK-CANONICAL-PACKAGES.md`.
- Post-deploy validation setup starts with
  `post-deploy-validation-integration-guide.md`.

## Active client docs

- `browser-dash-integration-guide.md` — primary browser/Dash onboarding guide:
  deploy output, bearer-header contract, asset wiring, uploader usage, and SDK
  choices.
- `CLIENT-SDK-CANONICAL-PACKAGES.md` — canonical package names and scope by
  language.
- `post-deploy-validation-integration-guide.md` — downstream reusable workflow
  setup for runtime validation.
- `dash-minimal-workflow.yml`
- `rshiny-minimal-workflow.yml`
- `react-next-minimal-workflow.yml`
- `examples/workflows/*`

## Authority / references

- `../overview/IMPLEMENTATION-STATUS-MATRIX.md`
- `../architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `../architecture/adr/ADR-0038-docs-authority-reset.md`
- `../architecture/spec/SPEC-0027-public-api-v2.md`
- `../architecture/spec/SPEC-0029-platform-serverless.md`
- `../architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `../contracts/deploy-output-authority-v2.schema.json`
- `../contracts/workflow-post-deploy-validate.schema.json`
- `../runbooks/release/release-runbook.md`

## Rule

Downstream examples must target the unified SDK packages, the browser-only
bridge surface, and the surviving reusable post-deploy validation workflow
only.
Downstream post-deploy validation should pass authoritative `deploy-output`
content directly through `deploy_output_json` or `deploy_output_path`; do not
assume a Nova GitHub deploy workflow run id exists.
When downstream automation needs the runtime base URL, it must derive that
authority from Nova `deploy-output.json` rather than treating a manually
entered `NOVA_API_BASE_URL` as the source of truth when deploy-output evidence
is available.
Browser upload flows must stay bearer-only: consumer apps obtain and refresh
tokens, then render the full `Authorization` header value into the hidden DOM
node read by `nova_dash_bridge`.
