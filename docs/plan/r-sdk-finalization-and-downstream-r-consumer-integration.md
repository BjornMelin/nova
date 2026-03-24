# R SDK Finalization and Downstream R Consumer Integration

Status: Completed wave record
Owner: Nova release architecture
Last updated: 2026-03-24

## Purpose

This document records the completed Nova R SDK finalization wave and the
downstream `ShinyAbsorberApp` and `UVAbsorbers` integration work. It is kept
for traceability, not as an active planning router.

## Phase 1: Nova execution checklist

- [x] Simplify the Nova R runtime to the current public contract:
  JSON request and response handling only, native `httr2` helpers, and one
  Nova-specific error condition.
- [x] Regenerate exported R wrappers with concrete OpenAPI parameter signatures
  instead of generic `path_params`, `query`, and `content_type` bags.
- [x] Simplify `scripts/release/generate_clients.py` so one R operation model
  drives wrapper rendering, package metadata, README/manual output, and tests.
- [x] Replace metadata-heavy R tests with behavior tests covering request
  construction, auth/header precedence, JSON encoding, timeout handling, and
  Nova error-envelope parsing.
- [x] Keep the signed-tarball, real-package, shared-R-check release posture
  intact.

## Phase 2: Nova docs and authority checklist

- [x] Rewrite package-local docs to match the final R SDK surface.
- [x] Update active Nova docs that describe R/Shiny clients and deploy
  validation so they match the final implementation.
- [x] Update existing requirements / ADR / SPEC authority docs in place rather
  than adding a new ADR.
- [x] Remove stale language implying a separate auth verify service or broader
  transport flexibility than Nova actually provides.

## Phase 3: ShinyAbsorberApp checklist

- [x] Remove the retired `nova-auth-api` verify contract and all
  `NOVA_AUTH_API_*` / `/v1/token/verify` references.
- [x] Add one app-owned Nova integration module built on `nova.sdk.r.file`.
- [x] Wire fail-closed Nova configuration into the real app bootstrap path.
- [x] Update app docs and deployment guidance to the real Nova bearer-JWT and
  base-URL contract.
- [x] Add and run tests covering bootstrap/config validation and the app-owned
  Nova client seam.

## Phase 4: UVAbsorbers checklist

- [x] Keep the scientific/package core separate from deployment and hosting
  concerns.
- [x] Add a thin, explicit Nova deployment/integration seam instead of mixing
  Nova logic into the domain functions.
- [x] Replace brittle AWS-only hardcoded deployment defaults with explicit
  configuration inputs where the final Nova integration requires them.
- [x] Update workflows, scripts, and docs to describe the canonical Nova-aware
  deployment and validation path.
- [x] Add and run tests covering the new deployment/config seam.

## Phase 5: Cross-repo verification checklist

- [x] Run Nova package tests, generator checks, docs/authority tests, and R
  conformance checks.
- [x] Run `ShinyAbsorberApp` package tests and package check.
- [x] Run `UVAbsorbers` package tests, package check, and deployment/runtime
  seam tests.
- [x] Remove stale `nova-auth-api`, `NOVA_AUTH_API_`, and `/v1/token/verify`
  references across all scoped repos.
- [x] Confirm the final docs, workflow examples, and test suites agree on the
  same Nova auth, SDK, deployment, and validation contract.

## Residual package-check notes

- `ShinyAbsorberApp` now completes `devtools::check(document = FALSE)` without
  errors or warnings. Residual NOTES are legacy package-quality issues outside
  the Nova seam: hidden `.claude`, undeclared namespace usage in existing app
  code, and global-variable visibility notes from unqualified Shiny/plot code.
- `UVAbsorbeR` now completes `devtools::test()` and `devtools::check(document =
  FALSE)` without errors, but the package still carries legacy WARNINGs/NOTEs
  unrelated to the Nova seam:
  non-portable historical file names, undocumented legacy data objects and Rd
  arguments, `jsonlite`/`ggthemes`/`scales` dependency hygiene, `qpdf` absence,
  and top-level package metadata/documentation debt.
