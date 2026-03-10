# Plan Index (Current State)

Status: Active planning and release index
Last updated: 2026-03-10

## Purpose

This file routes readers to the active planning, release, and history documents.
For architecture authority, use `../architecture/README.md`.
For operator runbooks, use `../runbooks/README.md`.

## Active Planning and Release Entry Points

- `../PRD.md`
- `../architecture/requirements.md`
- `../runbooks/README.md`
- `./release/RELEASE-RUNBOOK.md`
- `./release/RELEASE-POLICY.md`
- `./release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- `./release/release-promotion-dev-to-prod-guide.md`
- `./release/deploy-runtime-cloudformation-environments-guide.md`
- `./release/HARD-CUTOVER-CHECKLIST.md`
- `./release/RELEASE-VERSION-MANIFEST.md`

## Supporting Release Guides

Use these when you need environment setup, operator inputs, or break-glass
guidance:

- `./release/config-values-reference-guide.md`
- `./release/day-0-operator-checklist.md`
- `./release/aws-oidc-and-iam-role-setup-guide.md`
- `./release/aws-secrets-provisioning-guide.md`
- `./release/github-actions-secrets-and-vars-setup-guide.md`
- `./release/codeconnections-activation-and-validation-guide.md`
- `./release/troubleshooting-and-break-glass-guide.md`
- `./release/documentation-maintenance-guide.md`

## Current Planning Notes

- Active runtime authority is layered across route/API authority, runtime
  topology and safety, downstream validation, and adjacent deploy-governance.
- Runtime topology and safety authority uses `ADR-0025`, `ADR-0026`,
  `SPEC-0017`, `SPEC-0018`, `SPEC-0019`, and `SPEC-0020`.
- Downstream validation authority uses `ADR-0027`, `ADR-0028`, `ADR-0029`,
  `SPEC-0021`, `SPEC-0022`, and `SPEC-0023`.
- Release planning and apply paths must stay synchronized with the active docs
  routers and workflow contracts.
- Stable generated-client and conformance behavior remain part of release
  readiness, not a separate documentation model.

## Historical Planning Artifacts

- `./HISTORY-INDEX.md`
- `../architecture/adr/superseded/`
- `../architecture/spec/superseded/`
- `../history/2026-03-v1-hard-cut/`
- `../history/2026-02-cutover/`
