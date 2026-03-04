# Nova Operator Runbooks (Canonical)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-03

## Purpose

Canonical entrypoint for Nova-path operator runbooks.
All active release and delivery runbooks must live under `nova/docs/**`.

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
11. [Worker lane operations and failure handling](./worker-lane-operations-and-failure-handling.md)

## Authority Guardrail

For active Nova delivery operations, do not reference retired
`container-craft` operational docs as current instructions.
Historical references are allowed only under `docs/history/**`.

Active authority alignment for runbooks is governed by:

1. [ADR-0024](../architecture/adr/ADR-0024-layered-architecture-authority-pack.md)
2. [ADR-0025](../architecture/adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md)
3. [ADR-0026](../architecture/adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)
4. [SPEC-0020](../architecture/spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md)

## Related History

- `docs/plan/HISTORY-INDEX.md`
- `docs/history/2026-02-cutover/architecture/spec/`
