# Nova Documentation

Status: Active
Last reviewed: 2026-03-14

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

### Standards and engineering workflow

Use these when the question is about repo conventions, quality gates, generated
artifacts, or documentation synchronization:

- `./standards/README.md`
- `./standards/repository-engineering-standards.md`
- repo-root `.pre-commit-config.yaml` and `scripts/checks/*.sh` for local hook
  enforcement that mirrors the AGENTS task router

### Runbooks and release operations

Use these when the question is about deployment, promotion, validation, or
runtime operations:

- `./runbooks/README.md`
- `./plan/PLAN.md`
- `./plan/release/`

### Overview and product context

Use these when you need a higher-level mental model before reading the
authority docs:

- `./overview/NOVA-REPO-OVERVIEW.md`
- `./PRD.md`

### Historical material

Use these only for traceability, not as active authority:

- `./history/`
- `./plan/HISTORY-INDEX.md`
- `./architecture/adr/superseded/`
- `./architecture/spec/superseded/`

## Rules

- Active runtime and operator guidance belongs under root `docs/**`.
- Historical material belongs under `docs/history/**` or superseded ADR/SPEC
  paths.
- If a doc changes runtime behavior, contracts, or durable operator guidance,
  update the relevant router docs in the same PR.
- Adapter-boundary changes must keep `./architecture/README.md`,
  `ADR-0025`, and `SPEC-0017` aligned on `nova_dash_bridge ->
  nova_file_api.public` as the canonical in-process seam.
