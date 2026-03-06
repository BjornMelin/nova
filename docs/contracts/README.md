# WS6/WS8 Contract Schemas

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-06

## Purpose

Provide machine-readable JSON schema contracts for reusable post-deploy
workflow APIs, downstream size profiles, release artifacts, and committed
OpenAPI documents used by release and consumer integration gates.

## Schema Set

Canonical committed OpenAPI artifacts live under `packages/contracts/openapi/`:

- `../../packages/contracts/openapi/nova-file-api.openapi.json`
- `../../packages/contracts/openapi/nova-auth-api.openapi.json`

- `reusable-workflow-inputs-v1.schema.json`
  - Defines typed v1 reusable workflow input contracts for runtime deploy and
    prod promotion APIs.
- `reusable-workflow-outputs-v1.schema.json`
  - Defines typed v1 workflow output contracts for reusable deployment APIs.
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
  - WS5 browser/live validation gate artifact contract for dash-pca + Nova.
- `workflow-auth0-tenant-ops-v1.schema.json`
  - Workflow-specific contract schema for Auth0 tenant operation reusable APIs.
- `ssm-runtime-base-url-v1.schema.json`
  - SSM parameter path + HTTPS value contract for runtime deploy-validation base URLs.

## Workflow contract updates (2026-03-06)

- Worker runtime contract is canonicalized on `JOBS_*` environment settings
  with explicit `JOBS_RUNTIME_MODE=worker` and `JOBS_WORKER_UPDATE_TOKEN`.
- Worker executable contract is the packaged command `nova-file-worker`.
- Reusable deploy input contract requires explicit `approval_environment` for
  environment-gated deployments.
- Canonical file/auth OpenAPI artifacts are committed under
  `packages/contracts/openapi/` and are CI drift-gated.
- Canonical OpenAPI export drift is checked with
  `scripts/contracts/export_openapi.py --check`.
- Internal TypeScript/R generated catalog drift is checked with
  `scripts/release/generate_clients.py --check`.
- Committed Python SDK package drift is checked with
  `scripts/release/generate_python_clients.py --check`.
- Promotion input contract supports path-based payload sources
  (`*_path`) in addition to inline JSON payload fields.
- Promotion input contract requires SHA256 digests for
  `changed_units`, `version_plan`, and `promotion_candidates`.
- Reusable deploy-runtime output `manifest_sha256` is the canonical SHA256 of
  `docs/plan/release/RELEASE-VERSION-MANIFEST.md`, not deploy-evidence output.
- Deploy and release workflow contracts are concurrency-scoped and deploy via
  change-set create/update + pre-execution validation (`describe-events`,
  `OperationEvents`) + execute lifecycle with rollback-on-failure behavior.
- Post-deploy validation workflow contracts support dual-service validation
  inputs and artifact reports for both file and auth targets.

## Canonical SDK/contract verification flow

Run from repository root with `.venv` active:

```bash
source .venv/bin/activate && uv run python scripts/contracts/export_openapi.py --check
source .venv/bin/activate && uv run python scripts/release/generate_clients.py --check
source .venv/bin/activate && uv run python scripts/release/generate_python_clients.py --check
source .venv/bin/activate && uv run pytest -q packages/nova_file_api/tests/test_generated_client_smoke.py
```

The generated-client smoke suite covers both
`nova-file-api.openapi.json` and `nova-auth-api.openapi.json`.
Committed Python SDK trees are part of the drift-gated contract surface, not
an optional post-processing artifact.

## Related references

- `../clients/post-deploy-validation-integration-guide.md`
- `../plan/release/RELEASE-POLICY.md`
- `../architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`
- `../architecture/spec/SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md`
- `../architecture/spec/SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md`
- `../architecture/spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md`

## Versioning policy

- `v1` is the stable rolling compatibility channel.
- `v1.x.y` tags are immutable releases and are required for production pinning.
