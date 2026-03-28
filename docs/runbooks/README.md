# Nova operator runbooks

Status: Active
Current repository state: **pre-wave-2 implementation baseline**
Last reviewed: 2026-03-25

## Purpose

Route operators and implementation agents to the correct operational docs
without confusing current live runbooks with future target-state runbooks.

## Current live operations

Until the migration branches land, these remain the authoritative operator docs
for the current repo/platform shape:

- `provisioning/README.md`
- `release/README.md`
- `provisioning/deploy-runtime-cloudformation-environments.md`
- `provisioning/nova-cicd-end-to-end-deploy.md`
- `release/release-runbook.md`
- `release/release-policy.md`
- `worker-lane-operations-and-failure-handling.md`
- `observability-security-cost-baseline.md`

## Target-state operational guidance

Use this for planning and implementing the platform migration, not as the
current production runbook:

- `RUNBOOK-SERVERLESS-OPERATIONS.md`

## Rules

- current live operations follow the current implemented runbooks until the
  migration is actually complete
- target-state operational guidance is approved for implementation planning
- after the migration, move ECS-centric runbooks to history or mark them
  superseded in the same branch that changes the live platform
