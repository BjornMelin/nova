# Nova Operator Runbooks

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-10

## Purpose

Canonical entrypoint for Nova-path release, deployment, validation, and runtime
operations runbooks.

For architecture authority, use `../architecture/README.md`.
For deeper engineering workflow standards, use `../standards/README.md`.
Active runtime topology and safety authority uses `ADR-0025`, `ADR-0026`,
`SPEC-0017`, `SPEC-0018`, `SPEC-0019`, and `SPEC-0020`.
Active downstream validation authority uses `ADR-0027`, `ADR-0028`, `ADR-0029`,
`SPEC-0021`, `SPEC-0022`, and `SPEC-0023`.

## Release and Deployment

1. [Deploy runtime CloudFormation environments guide](../plan/release/deploy-runtime-cloudformation-environments-guide.md)
2. [Day-0 operator checklist](../plan/release/day-0-operator-checklist.md)
3. [Deploy Nova CI/CD end-to-end guide](../plan/release/deploy-nova-cicd-end-to-end-guide.md)
4. [Release runbook](../plan/release/RELEASE-RUNBOOK.md)
5. [Release policy](../plan/release/RELEASE-POLICY.md)
6. [Release promotion dev-to-prod guide](../plan/release/release-promotion-dev-to-prod-guide.md)

## Validation and Governance

1. [Non-prod live validation runbook](../plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md)
2. [Browser live validation checklist](../plan/release/BROWSER-LIVE-VALIDATION-CHECKLIST.md)
3. [Governance lock runbook](../plan/release/governance-lock-runbook.md)
4. [Auth0 CLI + a0deploy runbook](../plan/release/AUTH0-A0DEPLOY-RUNBOOK.md)
5. [Troubleshooting and break-glass guide](../plan/release/troubleshooting-and-break-glass-guide.md)

## Runtime Operations

1. [Worker lane operations and failure handling](./worker-lane-operations-and-failure-handling.md)
2. [Observability, security, and cost baseline](./observability-security-cost-baseline.md)

## Runbook Guardrails

- Active Nova operator instructions must resolve to paths under root `docs/**`.
- Historical references are allowed only under `docs/history/**` or through
  `docs/plan/HISTORY-INDEX.md`.
- Release runbooks define the canonical mixed-package publish path: Python
  distributions publish to CodeArtifact with `twine`, and TypeScript SDK
  packages publish to CodeArtifact npm as generated/private artifacts after
  staged subpath-contract validation.
- Local developer npm auth must stay repo-scoped: use
  `eval "$(npm run -s codeartifact:npm:env)"`, do not run
  `aws codeartifact login --tool npm` on a workstation, and keep the AWS CLI
  floor at v2.9.5 or newer when ephemeral CI shells use that command. See
  `../plan/release/RELEASE-RUNBOOK.md` for the canonical local flow.

## Related Entry Points

- `../README.md`
- `../architecture/README.md`
- `../standards/README.md`
- `../plan/PLAN.md`
- `../plan/HISTORY-INDEX.md`
