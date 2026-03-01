# Documentation Maintenance Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-02-24

## Purpose

Define documentation quality rules for release/provisioning docs.

## Naming rules

1. New documentation files must use kebab-case names.
2. Allowed exceptions:
   - `README.md`
   - existing historic release docs already referenced by automation and plans.
3. New docs must avoid uppercase file names.

## Required sections for operational guides

Every operator guide must include:

1. `Purpose`
2. `Prerequisites`
3. `Inputs`
4. `Step-by-step commands`
5. `Acceptance checks`
6. `References`

## Placeholder rules

1. Use placeholders for environment-specific values:
   - `${AWS_ACCOUNT_ID}`
   - `${AWS_REGION}`
   - `${PROJECT}`
2. Do not include live secret material in docs.

## Review cadence

1. Add `Last reviewed` date to each guide.
2. Re-review at least every 90 days or after any CI/CD contract change.


## Nova-path authority guardrail

1. Active Nova operator instructions must resolve to paths under `nova/docs/**`.
2. Do not link to retired `container-craft` Nova docs as current operational guidance.
3. Historical archive references are allowed only under `docs/history/**`.
4. Infra docs checks enforce this rule for active docs paths.
