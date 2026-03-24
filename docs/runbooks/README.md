# Nova Operator Runbooks

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-24

## Purpose

Canonical entrypoint for Nova-path release, deployment, validation, and runtime
operations runbooks.

For architecture authority and the canonical route chain, use
`../architecture/README.md`.
For deeper engineering workflow standards, use `../standards/README.md`.
For workflow and release schema contracts, use `../contracts/README.md`.

## Release and Deployment

Provisioning indexes: [`provisioning/README.md`](./provisioning/README.md). Release
indexes: [`release/README.md`](./release/README.md).

1. [Deploy runtime CloudFormation environments](provisioning/deploy-runtime-cloudformation-environments.md)
2. [Day-0 operator checklist](provisioning/day-0-operator-checklist.md)
3. [Docker Buildx and credential-helper setup](provisioning/docker-buildx-credential-helper-setup.md)
4. [Deploy Nova CI/CD end-to-end](provisioning/nova-cicd-end-to-end-deploy.md)
5. [Release runbook](release/release-runbook.md)
6. [Release policy](release/release-policy.md)
7. [Release promotion addendum](release/release-promotion-dev-to-prod.md)
8. [Runtime config contract](../release/runtime-config-contract.generated.md) (generated; [`docs/release/`](../release/README.md))

## Validation and Governance

1. [Non-prod live validation runbook](release/nonprod-live-validation-runbook.md)
2. [Browser live validation checklist](release/browser-live-validation-checklist.md)
3. [Governance lock and branch protection](release/governance-lock-and-branch-protection.md)
4. [Auth0 CLI + a0deploy runbook](release/auth0-a0deploy-runbook.md)
5. [Troubleshooting and break-glass](release/troubleshooting-and-break-glass.md)

## Runtime Operations

1. [Worker lane operations and failure handling](./worker-lane-operations-and-failure-handling.md)
2. [Observability, security, and cost baseline](./observability-security-cost-baseline.md)

## Runbook Guardrails

- Active Nova operator instructions must resolve to paths under root `docs/**`.
- Historical references are allowed only under `docs/history/**` (see
  [`../history/README.md`](../history/README.md) for bundle index).
- Runtime env/override lists in active runbooks must point back to
  `../release/runtime-config-contract.generated.md`, not fork into handwritten
  duplicates.
- Use deeper runbooks for execution detail:
  - `release/release-runbook.md` for release execution and npm/CodeArtifact rules
  - `provisioning/deploy-runtime-cloudformation-environments.md` for deploy-input behavior
  - `provisioning/docker-buildx-credential-helper-setup.md` for local Docker repair

## Related Entry Points

- `../README.md`
- `../architecture/README.md`
- `../standards/README.md`
- `../plan/PLAN.md`
