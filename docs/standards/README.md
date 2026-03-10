# Engineering Standards

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-10

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
- `../architecture/adr/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md` for older SDK topology context that still informs generated-surface review
- `./repository-engineering-standards.md` for the full gate matrix and documentation sync rules
- `../plan/release/RELEASE-RUNBOOK.md`
- `../plan/release/RELEASE-POLICY.md`

## Scope

These standards cover repo engineering workflow, generated artifact rules,
quality-gate routing, and documentation synchronization. They do not replace
the architecture authority docs.
