# Engineering standards

Status: Active
Current repository state: **mixed wave-2 implementation baseline**
Last reviewed: 2026-03-25

## Purpose

Route readers to engineering workflow standards while keeping current-baseline
rules separate from remaining legacy-retirement and target-state cleanup work.

## Read after `AGENTS.md`

1. `../../AGENTS.md`
2. `../README.md`
3. `../architecture/README.md`
4. `./repository-engineering-standards.md`
5. `./DECISION-FRAMEWORKS-GREENFIELD-2026.md` for the wave-2 decision logic

## Current baseline standards

The current repository follows the engineering workflow already reflected in the
tracked code, workflows, and docs. Use:

- `repository-engineering-standards.md`
- current CI/workflow files in `.github/workflows/`
- current release runbooks

## Target-state planning standards

Use these when reasoning about remaining wave-2 cleanup and legacy retirement:

- `DECISION-FRAMEWORKS-GREENFIELD-2026.md`
- `../overview/DEPENDENCY-LEVERAGE-AUDIT.md`
- `../overview/ENTROPY-REDUCTION-LEDGER.md`

## Rule

Do not reintroduce pre-wave-2 package, runtime, or CI assumptions into current
verification commands. Keep standards aligned to the repo as currently
implemented.
