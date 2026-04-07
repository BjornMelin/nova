# Client and downstream integration docs

Status: Active
Current repository state: **canonical wave-2 serverless baseline**
Last reviewed: 2026-04-07

## Start here

- Browser or Dash teams should begin with `browser-dash-integration-guide.md`.
  It is the primary onboarding path from Nova deploy output to a working
  uploader integration.
- SDK package selection starts with `CLIENT-SDK-CANONICAL-PACKAGES.md`.
- Post-deploy validation setup starts with
  `post-deploy-validation-integration-guide.md`.

## Active client docs

- `browser-dash-integration-guide.md` -- primary browser/Dash onboarding guide:
  deploy output, bearer-header contract, asset wiring, uploader usage, and SDK
  choices.
- `CLIENT-SDK-CANONICAL-PACKAGES.md` -- canonical package names and scope by
  language.
- `post-deploy-validation-integration-guide.md` -- downstream reusable workflow
  setup for runtime validation.
- `examples/workflows/dash-post-deploy-validate.yml`
- `examples/workflows/rshiny-post-deploy-validate.yml`
- `examples/workflows/react-next-post-deploy-validate.yml`

## Authority / references

- `../overview/IMPLEMENTATION-STATUS-MATRIX.md`
- `../architecture/requirements.md`
- `../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `../architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `../architecture/adr/ADR-0034-eliminate-auth-service-and-session-auth.md`
- `../architecture/adr/ADR-0035-replace-generic-jobs-with-export-workflows.md`
- `../architecture/adr/ADR-0036-dynamodb-idempotency-no-redis.md`
- `../architecture/adr/ADR-0037-sdk-generation-consolidation.md`
- `../architecture/adr/ADR-0038-docs-authority-reset.md`
- `../architecture/adr/ADR-0039-lambda-runtime-bootstrap-and-runtime-container.md`
- `../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `../architecture/spec/SPEC-0027-public-api-v2.md`
- `../architecture/spec/SPEC-0028-export-workflow-state-machine.md`
- `../architecture/spec/SPEC-0029-platform-serverless.md`
- `../architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `../architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`
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
Browser upload clients should honor additive initiate hints such as
`part_size_bytes`, `max_concurrency_hint`, `sign_batch_size_hint`,
`session_id`, `resumable_until`, `accelerate_enabled`, `checksum_algorithm`,
and `checksum_mode` instead of hard-coding multipart tuning.
Client integrations that inspect `GET /v1/capabilities/transfers` should treat
quota fields such as `active_multipart_upload_limit`,
`daily_ingress_budget_bytes`, and `sign_requests_per_upload_limit` as the
current effective envelope for one deployed environment, and should also
respect `large_export_worker_threshold_bytes` when coordinating downstream
large-export behavior.
