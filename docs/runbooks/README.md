# Nova Operator Runbooks (Canonical)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-02

## Purpose

This page is the canonical entrypoint for Nova-path operator runbooks.
All active release and delivery runbooks for Nova must live under `nova/docs/**`.

## Canonical runbook set

1. [CI/CD documentation index](../plan/release/documentation-index.md)
2. [Day-0 operator checklist](../plan/release/day-0-operator-checklist.md)
3. [Deploy Nova CI/CD end-to-end guide](../plan/release/deploy-nova-cicd-end-to-end-guide.md)
4. [Release promotion dev-to-prod guide](../plan/release/release-promotion-dev-to-prod-guide.md)
5. [Release runbook](../plan/release/RELEASE-RUNBOOK.md)
6. [Non-prod live validation runbook](../plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md)
7. [Troubleshooting and break-glass guide](../plan/release/troubleshooting-and-break-glass-guide.md)
8. [Auth0 CLI + a0deploy runbook](../plan/release/AUTH0-A0DEPLOY-RUNBOOK.md)
9. [Governance lock runbook](../plan/release/governance-lock-runbook.md)
10. [Worker lane operations and failure handling](./worker-lane-operations-and-failure-handling.md)

## Authority guardrail

For Nova delivery operations, do not reference or link to retired
`container-craft` Nova docs as active instructions.

Historical references are allowed only under `docs/history/**` for archive context.

## Related architecture authority

- [ADR-0014: container-craft absorption and retirement](../architecture/adr/ADR-0014-container-craft-capability-absorption-and-repo-retirement.md)
- [SPEC-0013: absorption execution spec](../architecture/spec/SPEC-0013-container-craft-capability-absorption-execution-spec.md)
- [SPEC-0014: capability inventory and absorption map](../architecture/spec/SPEC-0014-container-craft-capability-inventory-and-absorption-map.md)
