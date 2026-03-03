# Nova Operator Runbooks (Canonical)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-03

## Purpose

Canonical entrypoint for Nova-path operator runbooks.
All active release and delivery runbooks must live under `nova/docs/**`.

## Canonical runbook set

1. [Day-0 operator checklist](../plan/release/day-0-operator-checklist.md)
2. [Deploy Nova CI/CD end-to-end guide](../plan/release/deploy-nova-cicd-end-to-end-guide.md)
3. [Release promotion dev-to-prod guide](../plan/release/release-promotion-dev-to-prod-guide.md)
4. [Release runbook](../plan/release/RELEASE-RUNBOOK.md)
5. [Release policy](../plan/release/RELEASE-POLICY.md)
6. [Non-prod live validation runbook](../plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md)
7. [Troubleshooting and break-glass guide](../plan/release/troubleshooting-and-break-glass-guide.md)
8. [Auth0 CLI + a0deploy runbook](../plan/release/AUTH0-A0DEPLOY-RUNBOOK.md)
9. [Governance lock runbook](../plan/release/governance-lock-runbook.md)
10. [Worker lane operations and failure handling](./worker-lane-operations-and-failure-handling.md)

## Authority Guardrail

For active Nova delivery operations, do not reference retired
`container-craft` operational docs as current instructions.
Historical references are allowed only under `docs/history/**`.

## Related History

- `docs/plan/HISTORY-INDEX.md`
- `docs/history/2026-02-cutover/architecture/spec/`
