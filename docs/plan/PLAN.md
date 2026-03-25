# Plan Index

Status: Active planning and release index
Last updated: 2026-03-25

## Purpose

This file routes readers to active planning and release documents. For
architecture authority, use `../architecture/README.md`. For operator runbooks,
use `../runbooks/README.md`. Archived program material lives under
[`../history/README.md`](../history/README.md) only when you need traceability.
The active npm/TypeScript SDK workflow baseline is Node 24 LTS; use the
standards and release runbook docs for the authoritative operator details.

## Active Planning and Release Entry Points

- `../PRD.md`
- `../architecture/requirements.md`
- `../architecture/requirements-wave-2.md` (approved target-state planning supplement)
- `./GREENFIELD-WAVE-2-EXECUTION.md` (green-field v2 branch program)
- `../overview/CANONICAL-TARGET-2026-04.md` (approved target-state overview)
- `../overview/IMPLEMENTATION-STATUS-MATRIX.md` (current baseline vs target gap tracker)
- `./greenfield-simplification-program.md` (canonical green-field program router)
- `./greenfield-authority-map.md` (pack-ID translation and traceability map)
- `../runbooks/README.md`
- `../runbooks/release/README.md` (release validation and policy)
- `../runbooks/provisioning/README.md` (first-time deploy and CI/CD setup)
- `../release/README.md` (committed release artifacts: manifest, generated runtime contract)
- `../release/runtime-config-contract.generated.md` (env vars come from
  explicit `Settings.validation_alias` mappings)
- `../release/RELEASE-VERSION-MANIFEST.md`

## Supporting and Traceability Material

- `./greenfield-evidence/README.md` (supporting copies and audit artifacts; not
  active authority)
- `./r-sdk-finalization-and-downstream-r-consumer-integration.md` (completed
  wave record)
- `../history/README.md` (archive entrypoint)

## `docs/plan` directory layout

| Path | Role |
| --- | --- |
| `PLAN.md` | This index (active planning + release pointers) |
| `GREENFIELD-WAVE-2-EXECUTION.md` | Branch-ordered execution program for the green-field v2 hard cut |
| `greenfield-simplification-program.md` | Green-field program narrative and execution router |
| `greenfield-authority-map.md` | Maps historical pack IDs to canonical Nova ADRs and SPECs |
| `greenfield-evidence/` | Non-normative evidence pack copies; index at `greenfield-evidence/README.md` |
