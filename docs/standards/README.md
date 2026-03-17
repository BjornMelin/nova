# Engineering Standards

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-17

## Purpose

Canonical entrypoint for repo engineering standards that are too detailed for
`AGENTS.md` but still durable across sessions.

## Read This After `AGENTS.md`

Use these in order:

1. `../../AGENTS.md`
2. `../README.md`
3. `../architecture/README.md`
4. `../overview/NOVA-REPO-OVERVIEW.md`
5. `./repository-engineering-standards.md`
6. relevant ADR/SPEC authority docs for the change you are making
7. `../runbooks/README.md` when the task affects release or operations

## Key Deep References

- `../architecture/README.md` for active authority routing
- Active documentation must reference the single canonical route authority
  chain:
  - `../architecture/requirements.md`
  - `../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
  - `../architecture/spec/SPEC-0000-http-api-contract.md`
  - `../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `../architecture/adr/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md` for older SDK topology context that still informs generated-surface review
- `./repository-engineering-standards.md` for the full gate matrix and documentation sync rules
- `../plan/release/RELEASE-RUNBOOK.md`
- `../plan/release/RELEASE-POLICY.md`

## Scope

These standards cover repo engineering workflow, generated artifact rules,
quality-gate routing, pre-commit hook policy, and documentation
synchronization. They do not replace the architecture authority docs.

Durable operator inputs must stay synchronized across scripts, templates, and
docs. For runtime deploys, the ECS service stack now owns the repo-managed task
role and cache secret injection, so active docs and tests must reject
`TASK_ROLE_ARN`, `TASK_EXECUTION_SECRET_ARNS`, and
`TASK_EXECUTION_SSM_PARAMETER_ARNS`.
