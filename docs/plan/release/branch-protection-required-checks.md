# Branch Protection Required Checks (PR-05B/PR-05C)

This document defines the required status checks for protected branches so
cross-framework conformance is enforced before merge.

## Target branch

- `main`

## Required checks

From workflow `Nova CI` (`.github/workflows/ci.yml`):

- `quality-gates`

From workflow `Cross-Framework Conformance` (`.github/workflows/conformance.yml`):

- `dash-conformance`
- `shiny-conformance`
- `typescript-conformance`

## GitHub branch rule wiring

1. Open repository settings -> Branches -> Branch protection rules.
2. Edit the `main` rule (or create one if missing).
3. Enable **Require status checks to pass before merging**.
4. Add the checks listed above by exact name.
5. Enable **Require branches to be up to date before merging**.
6. Save and verify PRs show all required checks as blocking gates.

## Scope guardrails

TypeScript conformance lane scope is intentionally minimal:

- contract fixture typing
- SDK/client envelope verification
- auth verify + queue/transfer contract parity

No broad app feature tests are part of this required check set.
