# Workflow and release contract schemas

Status: Active
Current repository state: **canonical serverless baseline**
Last reviewed: 2026-04-10

## Current machine-readable contract set

These schemas remain the current machine-readable baseline contract artifacts:

- `release-artifacts-v1.schema.json`
- `deploy-output-authority-v2.schema.json` (published runtime provenance and
  canonical public base URL authority)
- `release-prep-v1.schema.json`
- `release-execution-manifest-v1.schema.json`
- `workflow-post-deploy-validate.schema.json`
- `workflow-auth0-tenant-deploy.schema.json`
- `browser-live-validation-report.schema.json`
- `workflow-auth0-tenant-ops-v1.schema.json`

## Approved breaking-change record for the current baseline

- `BREAKING-CHANGES-V2.md`

That file remains the authoritative human-readable ledger of the intentional
hard cuts and already-landed contract changes across the current baseline.

## Rule

Keep only schemas that describe surviving release, AWS-native post-merge
control-plane, release-prep metadata, release execution manifests, runtime
deploy provenance, validation, and Auth0 automation surfaces. Do not retain
machine-readable contracts for deleted GitHub release executors or any workflow
that writes release commits back to protected Git branches.
Treat `release-prep-v1` and `release-execution-manifest-v1` as complementary:
release prep captures the reviewed source commit, while the execution manifest
pins the merged deploy commit and validates ancestry between the two.
Do not treat execute-api hostnames as public runtime authority. When an
execute-api endpoint appears in deploy-output, it exists only to prove that the
default endpoint is blocked.
Post-deploy validation reports must retain both the public HTTPS route checks
and the transfer-policy envelope assertions. When a reusable workflow caller
provides a read-only AWS role, the same report also captures live AWS runtime
checks for concurrency, alarms, AppConfig rollout state, dashboard presence,
and transfer-budget notification wiring.
The generated runtime-config artifact in
`docs/contracts/runtime-config-contract.generated.md` is derived from
`packages/nova_file_api/src/nova_file_api/config.py` for supported runtime
settings and `infra/nova_cdk/src/nova_cdk/runtime_release_manifest.py` for the
deployed API/workflow Lambda env surface and validator-facing handler
inventory.

## Authority / canonical references

- `../architecture/requirements.md` -- requirements ledger that captures baseline
  architectural and contract assumptions.
- `../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md` -- canonical
  route-surface cut for V1 API and ops authorities.
- `../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md` -- route
  namespace guardrails for `v1/*` and literal capability boundaries.
- `../architecture/spec/SPEC-0027-public-api-v2.md` -- public API baseline with
  route and transport contracts (including `/v1/exports*`, `/v1/transfers/*`).
- `../architecture/spec/SPEC-0028-export-workflow-state-machine.md` -- downstream
  export workflow control contract in the green-field overlay range.
- `../architecture/spec/SPEC-0029-platform-serverless.md` -- serverless platform
  invariants for runtime and runtime-adjacent controls.
- `../architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md` -- canonical SDK
  generation and artifact layout constraints.
- `../architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md` -- docs/tests
  authority reset guidance.
- `../architecture/adr/ADR-0033-canonical-serverless-platform.md` -- overlay ADR for the
  canonical platform baseline.
- `../architecture/adr/ADR-0034-eliminate-auth-service-and-session-auth.md` -- overlay
  auth surface simplification and bearer-only posture.
- `../architecture/adr/ADR-0035-replace-generic-jobs-with-export-workflows.md` -- overlay
  hardens export-workflow-first integration semantics.
- `../architecture/adr/ADR-0036-dynamodb-idempotency-no-redis.md` -- overlay for
  idempotency and correctness model.
- `../architecture/adr/ADR-0037-sdk-generation-consolidation.md` -- overlay for SDK and
  generated contract alignment.
- `../architecture/adr/ADR-0038-docs-authority-reset.md` -- overlay docs authority
  governance chain.
