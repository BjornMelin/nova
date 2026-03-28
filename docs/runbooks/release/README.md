# Release runbooks (index)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-28

## Purpose

Canonical operator docs for package release execution, route validation,
governance, and auditability.

Committed release artifacts:

- [`../../release/README.md`](../../release/README.md)
- [`../../release/RELEASE-VERSION-MANIFEST.md`](../../release/RELEASE-VERSION-MANIFEST.md)
- [`../../release/runtime-config-contract.generated.md`](../../release/runtime-config-contract.generated.md)

## Core release docs

| Doc | Role |
| --- | --- |
| [release-policy.md](release-policy.md) | Release scope, package promotion, and security policy |
| [release-runbook.md](release-runbook.md) | Plan/apply/publish/promote execution path |
| [governance-lock-and-branch-protection.md](governance-lock-and-branch-protection.md) | Required checks and hosted branch policy |

## Validation and specialized docs

| Doc | Role |
| --- | --- |
| [browser-live-validation-checklist.md](browser-live-validation-checklist.md) | Browser-level verification checklist |
| [auth0-a0deploy-runbook.md](auth0-a0deploy-runbook.md) | Auth0 tenant ops workflow guidance |

## Rule

Keep this directory limited to the surviving GitHub workflow release surface.
Deleted deploy-runtime and pipeline-control-plane procedures are no longer
active runbooks.
