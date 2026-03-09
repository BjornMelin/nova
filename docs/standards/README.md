# Engineering Standards

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-09

## Purpose

Canonical entrypoint for deeper repo engineering/operator standards that are
too detailed for `AGENTS.md` but still durable across sessions.

## Read this after `AGENTS.md`

Use these in order:

1. `../../AGENTS.md`
2. `../../README.md`
3. `../overview/NOVA-REPO-OVERVIEW.md`
4. `./repository-engineering-standards.md`
5. relevant ADR/SPEC authority docs for the change you are making
6. `../runbooks/README.md` when the task affects release/operations

## Key deep references

- `../architecture/adr/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md`
- `../architecture/adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md`
- `../architecture/adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md`
- `../architecture/spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md`
- `../architecture/spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md`
- `../architecture/spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md`
- `../plan/release/RELEASE-RUNBOOK.md`
- `../plan/release/RELEASE-POLICY.md`

## Scope

These standards summarize repo engineering workflow, generated SDK rules,
quality gates, and documentation synchronization. They do not replace
architecture authority docs.
