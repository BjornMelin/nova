# Nova Operator Runbooks (Canonical)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-05

## Purpose

Canonical entrypoint for Nova-path operator runbooks.
All active release and delivery runbooks must live under `nova/docs/**`.
Deeper repo engineering/operator standards live under `docs/standards/**`.

## Canonical runbook set

1. [Deploy runtime CloudFormation environments guide](../plan/release/deploy-runtime-cloudformation-environments-guide.md)
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
`docs/plan/HISTORY-INDEX.md` is also an allowed canonical index into archived material.

Active authority alignment for runbooks is governed by:

1. [ADR-0023](../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)
2. [SPEC-0000](../architecture/spec/SPEC-0000-http-api-contract.md)
3. [SPEC-0016](../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)
4. [requirements.md](../architecture/requirements.md)
5. [ADR-0024](../architecture/adr/ADR-0024-layered-architecture-authority-pack.md)
6. [ADR-0025](../architecture/adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md)
7. [ADR-0026](../architecture/adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)
8. [ADR-0027](../architecture/adr/ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md)
9. [ADR-0028](../architecture/adr/ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md)
10. [ADR-0029](../architecture/adr/ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md)
11. [SPEC-0015](../architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md)
12. [SPEC-0016](../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)
13. [SPEC-0017](../architecture/spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md)
14. [SPEC-0018](../architecture/spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md)
15. [SPEC-0019](../architecture/spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md)
16. [SPEC-0020](../architecture/spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md)
17. [SPEC-0021](../architecture/spec/SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md)
18. [SPEC-0022](../architecture/spec/SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md)
19. [SPEC-0023](../architecture/spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md)

Release runbooks define the canonical mixed-package publish path:

- Python distributions publish to CodeArtifact with `twine`
- TypeScript SDK packages publish to CodeArtifact npm as generated/private
  artifacts after staged subpath-contract validation

Local developer npm auth for Nova must stay repo-scoped:

- use the repository helper `eval "$(npm run -s codeartifact:npm:env)"`
- this generates repo-local `.npmrc.codeartifact` and sets
  `NPM_CONFIG_USERCONFIG`
- do not run `aws codeartifact login --tool npm` on a workstation because it
  rewrites global `~/.npmrc` and affects unrelated repos
- when CI or ephemeral shells use `aws codeartifact login --tool npm`, npm 10.x
  requires AWS CLI v2.9.5 or newer
- see `../plan/release/RELEASE-RUNBOOK.md` for the canonical local flow

## Related History

- `docs/plan/HISTORY-INDEX.md`
- `docs/history/2026-02-cutover/architecture/spec/`
