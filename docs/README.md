# Nova Documentation

Status: Active
Last reviewed: 2026-03-22

## Purpose

This is the repo-wide documentation router. Start here when you need to find
the right authority document quickly without scanning the entire `docs/` tree.

## Reading Order for Fresh Sessions

1. `../AGENTS.md`
2. `./architecture/README.md`
3. `../README.md`
4. `./standards/README.md`
5. `./runbooks/README.md` when the task affects release or operations

## Documentation Map

### Architecture and authority

Use these when the question is about runtime contracts, topology, ownership, or
safety:

- `./architecture/README.md`
- `./architecture/requirements.md`
- `./architecture/adr/index.md`
- `./architecture/spec/index.md`

### SDK and release governance

Use these when the question is about SDK packaging, release-grade TypeScript,
or first-class internal R release artifacts:

- `./clients/README.md`
- `./architecture/adr/ADR-0038-sdk-architecture-by-language.md`
- `./architecture/spec/SPEC-0029-sdk-architecture-and-artifact-contract.md`
- `./architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`

### Standards and engineering workflow

Use these when the question is about repo conventions, quality gates, generated
artifacts, or documentation synchronization:

- `./standards/README.md`
- `./standards/repository-engineering-standards.md`
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
- `./plan/greenfield-authority-map.md`
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
  update the relevant router docs in the same PR.
- Runtime deploy docs must reflect that the ECS service stack owns the
  repo-managed task role and cache secret injection; active docs must not
  require `TASK_ROLE_ARN`, `TASK_EXECUTION_SECRET_ARNS`, or
  `TASK_EXECUTION_SSM_PARAMETER_ARNS`.
- Runtime config docs, deploy scripts, and infra tests must derive their live
  env/override matrix from `packages/nova_file_api/src/nova_file_api/config.py`
  plus `scripts/release/runtime_config_contract.py`, with
  `./release/runtime-config-contract.generated.md` treated as the
  operator-facing generated view.
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
