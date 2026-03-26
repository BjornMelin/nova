# Nova Operator Runbooks

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-25

## Purpose

Canonical entrypoint for Nova-path release, deployment, validation, and runtime
operations runbooks.
Operator tooling should assume Python 3.13 as the default local and primary
quality baseline, but active runtime package support begins at Python 3.11 and
the hosted compatibility lane covers Python 3.11 plus 3.12.

See `../architecture/README.md` for architecture authority and the canonical
route chain.
Consult `../standards/README.md` for deeper engineering workflow standards.
Reference `../contracts/README.md` for workflow and release schema contracts.

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
9. [Canonical serverless operations](RUNBOOK-SERVERLESS-OPERATIONS.md)

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
- Active runbooks must describe runtime env vars as coming from explicit
  `Settings.validation_alias` values in `config.py`; release tooling does not
  read `alias` or infer uppercase names.
- `RUNBOOK-SERVERLESS-OPERATIONS.md` plus `infra/nova_cdk/README.md` are the
  canonical path for new serverless environments.
- ECS/CloudFormation provisioning runbooks remain only for legacy environments
  that still depend on the older platform shape.
- Use deeper runbooks for execution detail:
  - `release/release-runbook.md` for release execution, the Node 24 LTS npm
    baseline, the current TypeScript 5.x line with TypeScript 6 explicitly
    deferred, and npm/CodeArtifact rules
  - `provisioning/deploy-runtime-cloudformation-environments.md` for deploy-input behavior
  - `provisioning/docker-buildx-credential-helper-setup.md` for local Docker repair

## Related Entry Points

- `../README.md`
- `../architecture/README.md`
- `../standards/README.md`
- `../plan/PLAN.md`
