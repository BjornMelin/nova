# Nova Documentation

Status: Active
Last reviewed: 2026-03-25

## Purpose

After [AGENTS.md](../AGENTS.md) (repo rules, commands, and guardrails), use this
file to pick the right authority document without scanning the entire `docs/`
tree.
Minimum supported Python version for workspace packages is 3.11; default local
tooling and the primary quality lane stay on Python 3.13, while compatibility
coverage now spans Python 3.11 and 3.12.

## Reading Order for Fresh Sessions

1. `../AGENTS.md` — entry point for agents and contributors
2. `./README.md` — this documentation map (you are here after step 1)
3. `./architecture/README.md`
4. `../README.md`
5. `./standards/README.md`
6. `./runbooks/README.md` when the task affects release or operations

## Documentation Map

### Architecture and authority

Use these when the question is about runtime contracts, topology, ownership, or
safety:

- `./architecture/README.md`
- `./architecture/requirements.md`
- `./architecture/adr/index.md`
- `./architecture/spec/index.md`

### SDK governance

Use these when the question is about SDK packaging, release-grade TypeScript,
or first-class internal R release artifacts:

- `./architecture/adr/ADR-0037-sdk-generation-consolidation.md`
- `./architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `./architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`

### Downstream consumer integration

Use these when the question is about reusable workflows, post-deploy
validation, or consumer-repo examples:

- `./clients/README.md`
- `./clients/post-deploy-validation-integration-guide.md`

### Contract schemas

Use these when the question is about machine-readable workflow, validation, or
release schema contracts:

- `./contracts/README.md`
- `./contracts/`

### Standards and engineering workflow

Use these when the question is about repo conventions, quality gates, generated
artifacts, or documentation synchronization:

- `./standards/README.md`
- `./standards/repository-engineering-standards.md`
- Node 24 LTS is the current npm/TypeScript SDK tooling baseline; see the
  standards and release runbook authority docs for the durable operator details
- The active workspace remains on the verified TypeScript 5.x line; TypeScript
  6 is deferred until a dedicated repo-wide migration updates generated SDKs,
  conformance fixtures, and release workflow docs together
- `.github/workflows/ci.yml` for the unified runtime, generated-client, and
  conformance check graph
- `.github/workflows/cfn-contract-validate.yml` for separate infra/docs
  contract validation
- repo-root `.pre-commit-config.yaml` and `scripts/checks/*.sh` for local hook
  enforcement that mirrors the AGENTS task router

### Runbooks and release operations

Use these when the question is about deployment, promotion, validation, or
runtime operations:

- `./runbooks/README.md`
- `./plan/PLAN.md`
- `./plan/greenfield-simplification-program.md`
- `./runbooks/release/` and `./runbooks/provisioning/` for narrative operator
  runbooks
- `./release/` for committed release artifacts (manifest, generated runtime
  contract markdown)
- `./release/runtime-config-contract.generated.md` for the generated runtime
  env/deploy matrix

### Overview and product context

Use these when you need a higher-level mental model before reading the
authority docs:

- `./overview/NOVA-REPO-OVERVIEW.md`
- `./PRD.md`

### Target-state planning supplements

Use these when planning or executing the green-field v2 hard-cut program. They
describe the approved target and current implementation gap; they do not by
themselves replace the current active authority/runtime docs:

- `./architecture/requirements-wave-2.md`
- `./overview/CANONICAL-TARGET-2026-04.md`
- `./overview/IMPLEMENTATION-STATUS-MATRIX.md`
- `./plan/GREENFIELD-WAVE-2-EXECUTION.md`
- `./contracts/BREAKING-CHANGES-V2.md`
- `./clients/CLIENT-SDK-CANONICAL-PACKAGES.md`

### Historical material

Use these only for traceability, not as active authority:

- `./history/` (see [`./history/README.md`](./history/README.md) for bundles)
- `./architecture/adr/superseded/`
- `./architecture/spec/superseded/`

## Rules

- Active runtime and operator guidance belongs under root `docs/**`.
- Historical material belongs under `docs/history/**` or superseded ADR/SPEC
  paths.
- If a doc changes runtime behavior, contracts, or durable operator guidance,
  update the current canonical routers and affected authority docs in the same
  PR. The exact required router set is owned by
  `./standards/repository-engineering-standards.md`.
- Runtime deploy docs must reflect that the ECS service stack owns the
  repo-managed task role, cache secret injection, and ECS infrastructure role
  resolution; active docs must not require `ECS_INFRASTRUCTURE_ROLE_ARN`,
  `TASK_ROLE_ARN`, `TASK_EXECUTION_SECRET_ARNS`, or
  `TASK_EXECUTION_SSM_PARAMETER_ARNS`.
- Runtime config docs, deploy scripts, and infra tests must derive their live
  env/override matrix from `packages/nova_file_api/src/nova_file_api/config.py`
  plus `scripts/release/runtime_config_contract.py`, with
  `./release/runtime-config-contract.generated.md` treated as the
  operator-facing generated view.
- Runtime settings must keep explicit string `validation_alias` mappings for
  stable env var names. Release tooling reads `validation_alias` only and must
  not fall back to `alias` or implicit uppercase field-name derivation.
- Adapter-boundary changes must keep `./architecture/README.md`,
  `./architecture/adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md`,
  and
  `./architecture/spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md`
  aligned on `nova_dash_bridge -> nova_file_api.public` as the canonical
  in-process seam.
- Async public-surface changes must also keep
  `./architecture/adr/ADR-0037-async-first-public-surface.md` and
  `./architecture/spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md`
  aligned on direct async FastAPI consumption, thin sync adapters only at
  true sync edges, and no bridge-local threadpool tuning config for the
  FastAPI surface.
- Cross-cutting FastAPI transport changes must also keep
  `./architecture/adr/ADR-0041-shared-pure-asgi-middleware-and-errors.md`
  aligned with `packages/nova_runtime_support` as the sole authority for
  shared outer-ASGI request context and exception registration.
