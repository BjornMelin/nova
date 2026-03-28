# Engineering standards

Status: Active
Current repository state: **pre-wave-2 implementation baseline**
Last reviewed: 2026-03-25

## Purpose

Route readers to engineering workflow standards while keeping current-baseline
rules separate from target-state decision frameworks.

## Read after `AGENTS.md`

1. `../../AGENTS.md`
2. `../README.md`
3. `../architecture/README.md`
4. `./repository-engineering-standards.md`
5. `./DECISION-FRAMEWORKS-GREENFIELD-2026.md` for the wave-2 decision logic

## Current baseline standards

The current repository still follows the existing engineering workflow until the
rebaseline branch lands. Use:

- `repository-engineering-standards.md`
- current CI/workflow files in `.github/workflows/`
- current release runbooks

## Target-state planning standards

Use these when reasoning about the wave-2 hard cut:

- `DECISION-FRAMEWORKS-GREENFIELD-2026.md`
- `../overview/DEPENDENCY-LEVERAGE-AUDIT.md`
- `../overview/ENTROPY-REDUCTION-LEDGER.md`

## Rule

Do not back-port target-state assumptions into current-baseline verification
commands unless the matching branch actually changes the repo/tooling.
