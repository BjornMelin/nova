# Nova architecture requirements

Status: Active
Repository state: **current implemented AWS-native serverless baseline**
Last reviewed: 2026-04-02

## Purpose

Define the active architectural requirements for Nova as it exists now. This
file is current-state authority, not a migration worksheet.

## Functional requirements

- Public API routes remain under `/v1/*` plus `/metrics/summary`.
- Public authentication remains bearer JWT only and is verified in-process by
  the FastAPI runtime.
- File transfer orchestration remains control-plane only: Nova issues presigned
  upload/download contracts and does not proxy bulk bytes.
- Async work remains explicit export workflow orchestration under
  `/v1/exports*`, backed by Step Functions and DynamoDB.
- Runtime deploy and validation authority remain bound to `deploy-output.json`
  plus `deploy-output.sha256` rather than free-text base URL inputs.

## Platform requirements

- The canonical runtime stays in `infra/nova_cdk` and deploys:
  - API Gateway Regional REST API
  - FastAPI on AWS Lambda
  - Step Functions Standard
  - DynamoDB for export/idempotency state
  - S3 for transfer/export artifact storage
- The `execute-api` default endpoint stays disabled.
- Production keeps Regional WAF enabled by default.
- Non-production keeps Regional WAF disabled by default unless explicitly
  enabled for a verification or hardening need.
- Reserved concurrency stays enabled by default, with production failing closed
  if it is disabled.

## Release and automation requirements

- GitHub remains responsible for PR CI, manual release-plan preview, reusable
  validation workflows, and Auth0 tenant operations only.
- AWS CodePipeline + CodeBuild remain the only supported post-merge publish,
  promote, and deploy executor.
- Release metadata remains committed under `release/`.
- Runtime deploy inputs remain account-neutral and tenant-neutral: account ids,
  Route 53 values, certificates, CodeConnections ARNs, CodeArtifact repos, and
  Auth0 tenant coordinates must stay configurable inputs, not hardcoded repo
  truth.

## Auth0 requirements

- Auth0 tenant-as-code remains driven by the shared template under
  `infra/auth0/tenant/tenant.yaml` plus environment mappings.
- The canonical automation path is:
  - `validate_auth0_contract`
  - `bootstrap_auth0_tenant`
  - `audit_auth0_tenant`
  - `run_auth0_deploy_cli`
- `auth0-python` is the canonical programmatic SDK for tenant bootstrap and
  audit.
- `auth0-deploy-cli` remains the canonical declarative import/export engine.
- GitHub-hosted Auth0 workflows must read credentials from environment-scoped
  secrets (`auth0-dev`, `auth0-pr`, `auth0-qa`), not repo-wide Auth0 secrets.

## Cost and simplicity requirements

- Prefer one canonical implementation per concern.
- Default non-prod safety controls to the cheapest still-correct posture.
- Do not keep fallback publish/deploy executors alive once the AWS-native path
  exists.
- Prefer deletion of dead workflow, IAM, and infra surfaces over compatibility
  shims.

## Temporary exception tracking

- The first production custom-domain cutover may use wildcard browser CORS
  (`allowed_origins=["*"]`) to reduce launch friction.
- That exception is temporary and is tracked by GitHub issue `#111`:
  `Harden prod CORS origins after initial api-nova cutover`.

## Quality requirements

- Active docs must describe implemented state, not target-state aspiration.
- Generated contracts and generated docs must be derived from canonical sources
  and updated in the same change set as source changes.
- Infra, workflow, and docs contract tests must remain authoritative and
  deterministic.
- Personal-account values may appear in live operators’ local env files and AWS
  parameters, but active repo docs/examples should use placeholders unless a
  concrete live example is explicitly labeled as such.
