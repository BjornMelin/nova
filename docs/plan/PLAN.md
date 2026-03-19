# Plan Index (Current State)

Status: Active planning and release index
Last updated: 2026-03-19

## Purpose

This file routes readers to active planning and release documents. For
architecture authority, use `../architecture/README.md`. For operator runbooks,
use `../runbooks/README.md`. Archived program material lives under
[`../history/README.md`](../history/README.md) only when you need traceability.

## Active Planning and Release Entry Points

- `../PRD.md`
- `../architecture/requirements.md`
- `./greenfield-simplification-program.md` (canonical green-field program router)
- `./greenfield-authority-map.md` (ADR/SPEC index map for the program)
- `./greenfield-evidence/README.md` (supporting audit and scoring **copies**;
  non-authoritative—see table there for `EXECUTIVE_AUDIT.md`, CSV manifests, and
  related artifacts)
- `../runbooks/README.md`
- `../runbooks/release/README.md` (release validation and policy)
- `../runbooks/provisioning/README.md` (first-time deploy and CI/CD setup)
- `../release/README.md` (committed release artifacts: manifest, generated runtime contract)
- `../release/runtime-config-contract.generated.md`
- `../release/RELEASE-VERSION-MANIFEST.md`

## Supporting release guides

Full catalog: [`../runbooks/README.md`](../runbooks/README.md). Machine-stable
paths: [`../release/README.md`](../release/README.md).
Release/provisioning doc conventions: **Release operator docs profile** in
[`../standards/repository-engineering-standards.md`](../standards/repository-engineering-standards.md).

## `docs/plan` directory layout

| Path | Role |
| --- | --- |
| `PLAN.md` | This index (active planning + release pointers) |
| `greenfield-simplification-program.md` | Green-field program narrative and execution router |
| `greenfield-authority-map.md` | Maps program workstreams to ADRs and SPECs |
| `greenfield-evidence/` | Non-normative evidence pack copies; index at `greenfield-evidence/README.md` |

## Current Planning Notes

- Green-field simplification is an active program: single public runtime auth,
  bearer JWT scope from claims, direct worker persistence, native OpenAPI,
  shared pure ASGI middleware, async-first `nova_file_api.public`, TS/R/Python
  SDK stack cuts, infra narrative alignment, and final repo rebaseline. Start
  at `./greenfield-simplification-program.md` and `../architecture/adr/index.md`
  (`ADR-0033`–`ADR-0041`) plus `SPEC-0027`–`SPEC-0029`.
- Active runtime authority is layered across route/API authority, runtime
  topology and safety, downstream validation, and adjacent deploy-governance.
- `nova_dash_bridge` remains adapter-only and now consumes canonical in-process
  transfer contracts through `nova_file_api.public`.
- Runtime topology and safety authority uses `ADR-0025`, `ADR-0026`,
  `SPEC-0017`, `SPEC-0018`, `SPEC-0019`, and `SPEC-0020`.
- Downstream validation authority uses `ADR-0027`, `ADR-0028`, `ADR-0029`,
  `SPEC-0021`, `SPEC-0022`, and `SPEC-0023`.
- Release planning and apply paths must stay synchronized with the active docs
  routers and workflow contracts.
- Runtime deploy/config planning now uses the generated runtime config contract
  as the live env/override matrix, with `Settings` plus curated deploy
  metadata remaining the underlying authority.
- SDK planning now treats TypeScript as release-grade within Nova's existing
  CodeArtifact staged/prod system while keeping it generator-owned and
  subpath-only, and treats R as a first-class internal release artifact line
  with real packages, logical format `r`, CodeArtifact generic transport, and
  signed tarball evidence.
- Runtime deploy planning now assumes `infra/runtime/ecs/service.yml` owns the
  ECS service task role and cache secret injection; operator plans must not
  depend on `TASK_ROLE_ARN`, `TASK_EXECUTION_SECRET_ARNS`, or
  `TASK_EXECUTION_SSM_PARAMETER_ARNS`.
- Stable generated-client and conformance behavior remain part of release
  readiness, not a separate documentation model.
- Repo-local pre-commit hooks now mirror the AGENTS task router, and `ty` is
  now part of the required typing contract enforced by the main quality gates.
