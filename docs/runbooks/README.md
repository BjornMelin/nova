# Nova Operator Runbooks (Canonical)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-06

## Purpose

Canonical entrypoint for Nova-path operator runbooks.
All active release and delivery runbooks must live under `nova/docs/**`.

## Canonical runbook set

1. [Deploy runtime CloudFormation environments guide](../plan/release/deploy-runtime-cloudformation-environments-guide.md)
   Canonical operator script: `scripts/release/deploy-runtime-cloudformation-environment.sh`
2. [Day-0 operator checklist](../plan/release/day-0-operator-checklist.md)
3. [Deploy Nova CI/CD end-to-end guide](../plan/release/deploy-nova-cicd-end-to-end-guide.md)
4. [Release promotion dev-to-prod guide](../plan/release/release-promotion-dev-to-prod-guide.md)
5. [Release runbook](../plan/release/RELEASE-RUNBOOK.md)
6. [Release policy](../plan/release/RELEASE-POLICY.md)
7. [Non-prod live validation runbook](../plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md)
8. [Troubleshooting and break-glass guide](../plan/release/troubleshooting-and-break-glass-guide.md)
9. [Auth0 CLI + a0deploy runbook](../plan/release/AUTH0-A0DEPLOY-RUNBOOK.md)
10. [Governance lock runbook](../plan/release/governance-lock-runbook.md)
11. [Browser live validation checklist](../plan/release/BROWSER-LIVE-VALIDATION-CHECKLIST.md)
12. [Worker lane operations and failure handling](./worker-lane-operations-and-failure-handling.md)

## Authority Guardrail

For active Nova delivery operations, do not reference retired legacy
deployment operational docs as current instructions.
Historical references are allowed only under `docs/history/**`.
Superseded ADR/SPEC references are allowed only under
`docs/architecture/adr/superseded/**` and
`docs/architecture/spec/superseded/**`.

Active authority alignment for runbooks is governed by:

1. [ADR-0024](../architecture/adr/ADR-0024-layered-architecture-authority-pack.md)
2. [ADR-0025](../architecture/adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md)
3. [ADR-0026](../architecture/adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)
4. [ADR-0027](../architecture/adr/ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md)
5. [ADR-0028](../architecture/adr/ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md)
6. [ADR-0029](../architecture/adr/ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md)
7. [SPEC-0020](../architecture/spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md)
8. [SPEC-0021](../architecture/spec/SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md)
9. [SPEC-0022](../architecture/spec/SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md)
10. [SPEC-0023](../architecture/spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md)

Adjacent deploy-control-plane authority:

1. [ADR-0030](../architecture/adr/ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md)
2. [ADR-0031](../architecture/adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)
3. [ADR-0032](../architecture/adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)
4. [SPEC-0024](../architecture/spec/SPEC-0024-cloudformation-module-contract.md)
5. [SPEC-0025](../architecture/spec/SPEC-0025-reusable-workflow-integration-contract.md)
6. [SPEC-0026](../architecture/spec/SPEC-0026-ci-cd-iam-least-privilege-matrix.md)

Release runbooks define the canonical mixed-package publish path:

- Python distributions publish to CodeArtifact with `twine`
- TypeScript foundations publish to CodeArtifact npm after workspace-local
  source-dependency rewrite and staged install smoke validation

Local developer npm auth for Nova must stay repo-scoped:

- use the repository helper `eval "$(npm run -s codeartifact:npm:env)"`
- this generates repo-local `.npmrc.codeartifact` and sets
  `NPM_CONFIG_USERCONFIG`
- do not run `aws codeartifact login --tool npm` on a workstation because it
  rewrites global `~/.npmrc` and affects unrelated repos
- see `../plan/release/RELEASE-RUNBOOK.md` for the canonical local flow

## Related History

- `docs/plan/HISTORY-INDEX.md`
- `docs/history/2026-02-cutover/architecture/spec/`
