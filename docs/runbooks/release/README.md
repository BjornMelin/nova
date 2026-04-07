# Release runbooks (index)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-04-07

## Purpose

Canonical operator docs for package release execution, runtime validation,
governance, and auditability.

## Canonical documentation authority chain

1. `AGENTS.md`
2. `docs/README.md`
3. `docs/architecture/README.md`
4. active ADRs under `docs/architecture/adr/` and active specs under `docs/architecture/spec/`
5. `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
6. `release/README.md` for machine-owned release metadata surfaces
7. this runbook index plus the specific release/provisioning runbook you need

Committed release artifacts:

- [`../../../release/README.md`](../../../release/README.md)
- [`../../../release/RELEASE-PREP.json`](../../../release/RELEASE-PREP.json)
- [`../../../release/RELEASE-VERSION-MANIFEST.md`](../../../release/RELEASE-VERSION-MANIFEST.md)
- [`../../contracts/runtime-config-contract.generated.md`](../../contracts/runtime-config-contract.generated.md)

The public API Lambda zip is not a committed repo artifact. The AWS-native
release control plane builds it from the merged release PR commit, uploads it
to the release artifact bucket, and records the handoff in the S3-backed
release execution manifest. GitHub no longer owns supported publish, deploy,
or promotion execution paths.

Runtime-only CDK deploys are not supposed to synthesize
`NovaReleaseControlPlaneStack`. That path should require runtime inputs only;
release stack synthesis requires the release-control inputs, including
`RELEASE_CONNECTION_ARN`.

## Core release docs

| Doc | Role |
| --- | --- |
| [release-policy.md](release-policy.md) | Release scope, package promotion, and security policy |
| [release-runbook.md](release-runbook.md) | Human release-prep plus AWS publish/promote/deploy execution path |
| [governance-lock-and-branch-protection.md](governance-lock-and-branch-protection.md) | Required checks and hosted branch policy |

## Validation and specialized docs

| Doc | Role |
| --- | --- |
| [browser-live-validation-checklist.md](browser-live-validation-checklist.md) | Browser-level verification checklist |
| [auth0-a0deploy-runbook.md](auth0-a0deploy-runbook.md) | Auth0 tenant ops workflow guidance |

## Rule

Keep this directory limited to the surviving human GitHub release-prep flow,
the AWS-native post-merge control plane, and runtime validation surfaces.
Do not document deleted GitHub publish/deploy/promote executor workflows as
supported operator paths.
