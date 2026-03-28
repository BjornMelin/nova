# Nova documentation router

Status: Active
Current repository state: **pre-wave-2 implementation baseline**
Last reviewed: 2026-03-25

## Purpose

This file routes readers to the right documentation set without letting
pre-implementation baseline facts, approved target-state decisions, and
historical bundles blur together.

## Read in order

1. `../AGENTS.md`
2. `./architecture/README.md`
3. `./overview/IMPLEMENTATION-STATUS-MATRIX.md`
4. `../README.md`
5. `./standards/README.md`
6. `./runbooks/README.md` for current operations
7. `.agents/AUDIT_DELIVERABLES/README_RUN_ORDER.md` for branch execution

## Current implemented baseline

Use these when you need the truth about the repository **before** the wave-2
implementation branches land:

- `./architecture/README.md`
- `./overview/IMPLEMENTATION-STATUS-MATRIX.md`
- `./runbooks/README.md`
- `./contracts/README.md`
- `./overview/NOVA-REPO-OVERVIEW.md`

## Approved target-state program

Use these when you are planning or implementing the hard-cut modernization:

- `./overview/CANONICAL-TARGET-2026-04.md`
- `./architecture/requirements-wave-2.md`
- `./architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `./architecture/adr/ADR-0034-eliminate-auth-service-and-session-auth.md`
- `./architecture/adr/ADR-0035-replace-generic-jobs-with-export-workflows.md`
- `./architecture/adr/ADR-0036-dynamodb-idempotency-no-redis.md`
- `./architecture/adr/ADR-0037-sdk-generation-consolidation.md`
- `./architecture/adr/ADR-0038-docs-authority-reset.md`
- `./architecture/spec/SPEC-0027-public-api-v2.md`
- `./architecture/spec/SPEC-0028-export-workflow-state-machine.md`
- `./architecture/spec/SPEC-0029-platform-serverless.md`
- `./architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `./architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`
- `./plan/GREENFIELD-WAVE-2-EXECUTION.md`
- `.agents/AUDIT_DELIVERABLES/`

## Current authority indexes

- `./architecture/adr/index.md`
- `./architecture/spec/index.md`
- `./overview/ACTIVE-DOCS-INDEX.md`

## Supporting references

- `./architecture/spec/REFERENCES.md`
- `./overview/DEPENDENCY-LEVERAGE-AUDIT.md`
- `./overview/ENTROPY-REDUCTION-LEDGER.md`
- `./standards/DECISION-FRAMEWORKS-GREENFIELD-2026.md`

## Historical / superseded

Use only for audit trail or traceability:

- `./history/README.md`
- `./architecture/adr/superseded/`
- `./architecture/spec/superseded/`

## Rules

- Never treat `docs/history/**` or superseded ADR/SPEC paths as current
  authority.
- Current operations use the current implemented runbooks until the migration
  branches land.
- Implementation branches use the approved target-state ADR/SPEC set and the
  `.agents/AUDIT_DELIVERABLES/` prompts.
- When a branch lands, update status language so docs keep matching reality.
