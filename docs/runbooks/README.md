# Nova operator runbooks

Status: Active
Current repository state: **mixed wave-2 implementation with legacy runtime leftovers**
Last reviewed: 2026-03-25

## Purpose

Route operators and implementation agents to the correct operational docs
without confusing current live runbooks with future target-state runbooks.

## Current live operations

These remain authoritative for the current repo/platform shape, including the
mixed-wave-2 baseline and any still-running legacy environments:

- `provisioning/README.md`
- `release/README.md`
- `provisioning/deploy-runtime-cloudformation-environments.md`
- `provisioning/nova-cicd-end-to-end-deploy.md`
- `release/release-runbook.md`
- `release/release-policy.md`
- `worker-lane-operations-and-failure-handling.md`
- `observability-security-cost-baseline.md`

## Target-state operational guidance

Use this for the landed serverless platform components and for planning the
remaining legacy-runtime retirement work:

- `RUNBOOK-SERVERLESS-OPERATIONS.md`

## Rules

- current live operations follow the current implemented runbooks for both the
  landed serverless components and any still-active legacy environments
- serverless operational guidance is no longer future-state-only; it is part
  of the current mixed baseline
- after the migration, move ECS-centric runbooks to history or mark them
  superseded in the same branch that changes the live platform
