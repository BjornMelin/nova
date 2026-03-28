# Engineering Standards

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-25

## Purpose

Canonical entrypoint for repo engineering standards that are too detailed for
`AGENTS.md` but still durable across sessions.
Workspace packages support Python 3.11+, while the default developer and
primary quality baseline remains Python 3.13 with compatibility coverage on
Python 3.11 and 3.12.

## Read This After `AGENTS.md`

Use these in order:

1. `../../AGENTS.md`
2. `../README.md`
3. `../architecture/README.md`
4. `./repository-engineering-standards.md`
5. relevant ADR/SPEC authority docs for the change you are making
6. `../runbooks/README.md` when the task affects release or operations

## Key Deep References

- `../architecture/README.md` for active authority routing
- `../architecture/adr/ADR-0037-sdk-generation-consolidation.md`,
  `../architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md`, and
  `../architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md`
  for current SDK governance (superseded predecessors: `../architecture/adr/index.md`
  and `../architecture/spec/index.md`)
- `./repository-engineering-standards.md` for the full gate matrix and documentation sync rules
- `../contracts/README.md` for workflow, validation, and release schema catalogs
- `../release/README.md` for committed release artifacts (manifest, generated contract)
- `../runbooks/release/release-runbook.md`
- `../runbooks/release/release-policy.md`
- `../runbooks/release/README.md` and `../runbooks/provisioning/README.md` for narrative runbooks
- Release doc conventions: **Release operator docs profile** in
  `./repository-engineering-standards.md`

## Scope

These standards cover repo engineering workflow, generated artifact rules,
quality-gate routing, pre-commit hook policy, and documentation
synchronization. They do not replace the architecture authority docs.
The active CI layout uses a unified `Nova CI` workflow for runtime,
generated-client, and conformance checks. Within that workflow, `quality-gates`
owns lint/type/generation checks, dedicated `pytest-*` jobs own Python test
execution, and a non-required `pytest-report` job publishes merged report-only
coverage. `CFN Contract Validate` remains the separate infra/docs governance
workflow.
Node 24 LTS is the current npm/TypeScript SDK tooling baseline for local,
CI, and release lanes. The merged workspace remains on the verified
TypeScript 5.x line; TypeScript 6 is deferred until a repo-wide verified
migration lands.

Durable operator inputs must stay synchronized across scripts, templates, and
docs. For runtime deploys, the ECS service stack now owns the repo-managed task
role and cache secret injection, and the deploy operator resolves the ECS
infrastructure role from the Nova IAM control-plane stack, so active docs and
tests must reject `ECS_INFRASTRUCTURE_ROLE_ARN`, `TASK_ROLE_ARN`,
`TASK_EXECUTION_SECRET_ARNS`, and `TASK_EXECUTION_SSM_PARAMETER_ARNS`.

Runtime config drift guard:

- keep `packages/nova_file_api/src/nova_file_api/config.py` and
  `scripts/release/runtime_config_contract.py` aligned as the source-of-truth
  pair
- require explicit string `validation_alias` values for runtime settings and
  treat those aliases as the only contract-extraction input
- refresh `../release/runtime-config-contract.generated.md` with
  `scripts/release/generate_runtime_config_contract.py`
- treat the current runtime dependency floors as manifest-owned authority:
  `pydantic-settings>=2.13.1` in the surviving runtime packages and
  `uvicorn[standard]>=0.42.0` in `nova-file-api`
