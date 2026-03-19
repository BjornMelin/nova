# Nova Operator Runbooks

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-17

## Purpose

Canonical entrypoint for Nova-path release, deployment, validation, and runtime
operations runbooks.

For architecture authority, use `../architecture/README.md`.
For deeper engineering workflow standards, use `../standards/README.md`.
Active documentation must reference the single canonical route authority chain:
`../architecture/requirements.md`,
`../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`,
`../architecture/spec/SPEC-0000-http-api-contract.md`, and
`../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`.
Active runtime topology and safety authority uses `ADR-0025`, `ADR-0026`,
`SPEC-0017`, `SPEC-0018`, `SPEC-0019`, and `SPEC-0020`.
Active downstream validation authority uses `ADR-0027`, `ADR-0028`, `ADR-0029`,
`SPEC-0021`, `SPEC-0022`, and `SPEC-0023`.
Green-field simplification authority uses `ADR-0033` through `ADR-0041`,
`SPEC-0027` through `SPEC-0029`, and `../plan/greenfield-simplification-program.md`.

## Release and Deployment

Provisioning indexes: [`provisioning/README.md`](./provisioning/README.md). Release
indexes: [`release/README.md`](./release/README.md).

1. [Deploy runtime CloudFormation environments](provisioning/deploy-runtime-cloudformation-environments.md)
2. [Day-0 operator checklist](provisioning/day-0-operator-checklist.md)
3. [Docker Buildx and credential-helper setup](provisioning/docker-buildx-credential-helper-setup.md)
4. [Deploy Nova CI/CD end-to-end](provisioning/nova-cicd-end-to-end-deploy.md)
5. [Release runbook](release/release-runbook.md)
6. [Release policy](release/release-policy.md)
7. [Release promotion dev→prod](release/release-promotion-dev-to-prod.md)
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
- Historical references are allowed only under `docs/history/**` or through
  `docs/plan/HISTORY-INDEX.md`.
- Local developer hook bootstrap now uses repo-root pre-commit configuration
  plus `scripts/dev/install_hooks.sh`; `ty` is enforced through the required
  local and CI typing gates inside the standard quality lane.
- Release runbooks define the canonical mixed-package publish path: Python
  distributions publish to CodeArtifact with `twine`, and TypeScript SDK
  packages publish to CodeArtifact npm as generated/private artifacts after
  staged subpath-contract validation.
- Runtime deploy runbooks must treat the ECS service task role as repo-managed
  infrastructure owned by `infra/runtime/ecs/service.yml`; do not document or
  require `TASK_ROLE_ARN`, `TASK_EXECUTION_SECRET_ARNS`, or
  `TASK_EXECUTION_SSM_PARAMETER_ARNS`.
- Runtime env/override lists in active runbooks must resolve back to the
  generated runtime config contract at
  `../release/runtime-config-contract.generated.md`, not to hand-maintained
  duplicates.
- Local developer npm auth must stay repo-scoped: use
  `eval "$(npm run -s codeartifact:npm:env)"`, do not run
  `aws codeartifact login --tool npm` on a workstation, and keep the AWS CLI
  floor at v2.9.5 or newer when ephemeral CI shells use that command. See
  [`release/release-runbook.md`](./release/release-runbook.md) for the canonical local flow.

## Related Entry Points

- `../README.md`
- `../architecture/README.md`
- `../standards/README.md`
- `../plan/PLAN.md`
- `../plan/HISTORY-INDEX.md`
