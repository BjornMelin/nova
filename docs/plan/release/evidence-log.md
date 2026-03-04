# Release Evidence Log

Status: Active
Owner: Release Architecture + Platform Operations
Last updated: 2026-03-04

This file is the canonical active location for live validation and release
promotion evidence links.

## Entry Template

For each validation/promotion execution, append:

- date/time (UTC)
- operator
- environment (`dev` or `prod`)
- gate or workflow name
- pass/fail result
- artifact/log links
- remediation notes (if failed)

## 2026-03

- `2026-03-03T08:29:33Z` | operator: `openclaw-project-operator-role` |
  environment: `dev` | gate: `WS4 preflight (A/B/E permissions + role)`
  | result: `BLOCKED`
  - artifact/log links:
    - `.agents/plans/2026-03-03-nova-full-cross-repo-spec-orchestration.md`
      (`0.1` A5 row + `0.3` WS4 blocker evidence)
  - remediation notes:
    - Create Batch-B operator role by applying
      `infra/nova/nova-iam-roles.yml` with `BatchBOperatorPrincipalArn`
      populated.
    - Grant/read path for:
      `codeconnections:GetConnection`,
      `codepipeline:ListPipelineExecutions`,
      `codepipeline:GetPipelineState`,
      `codedeploy:ListApplications`.
    - Re-run Gate A-E per
      `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`.

- `2026-03-03T09:32:00Z` | operator: `AWSReservedSSO_PowerUserAccess (bjorn-dev)` |
  environment: `dev` | gate: `WS4 rerun + WS4 template apply`
  | result: `PARTIAL/BLOCKED`
  - artifact/log links:
    - `.agents/plans/2026-03-03-nova-full-cross-repo-spec-orchestration.md`
      (`0.1` A13/A15 rows + `0.3` WS4 rerun/template-apply entries)
  - remediation notes:
    - Gate A read checks now pass (`ConnectionStatus=AVAILABLE`, pipeline execution
      history visible).
    - `nova-ci-nova-ci-cd` stack update is blocked by denied
      `iam:PassRole` on `arn:aws:iam::099060980393:role/nova-ci-nova-codepipeline-role`.
    - Pipeline `ValidateDev` still fails with
      `YAML_FILE_ERROR` (`buildspecs/buildspec-deploy-validate.yml` not found)
      because Validate actions still consume `BuildOutput`.
    - `DevServiceBaseUrl` is currently `https://httpbin.org/anything`; direct
      probes returned `200` for both canonical and legacy paths, so route-authority
      behavior cannot be validated from this endpoint.
    - Runtime deployment inventory is not present (`ecs list-clusters` empty,
      `deploy list-applications` empty), so Gate B/C/D/E cannot be fully closed.

- `2026-03-03T09:32:00Z` | operator: `AWSReservedSSO_PowerUserAccess (bjorn-dev)` |
  environment: `dev` | gate: `WS6 dash-pca Run2`
  | result: `PASS`
  - artifact/log links:
    - `.agents/plans/2026-03-03-nova-full-cross-repo-spec-orchestration.md`
      (`0.1` A14/A17 rows + `0.3` WS6 Run2 entries)
  - remediation notes:
    - `uv.lock` refreshed against authenticated CodeArtifact index.
    - non-e2e suite passed (`371 passed, 1 skipped`).
    - e2e suite passed after fixture fix in `tests/e2e/conftest.py`
      (`1 passed, 4 skipped`).

- `2026-03-04T02:38:09Z` | operator: `AWSReservedSSO_AdministratorAccess (bjorn-dev)` |
  environment: `dev/prod planning` | gate: `runtime reproducibility hardening`
  | result: `PASS`
  - artifact/log links:
    - `infra/runtime/ecs/cluster.yml` (portable ALB ingress source contract)
    - `docs/plan/release/deploy-runtime-cloudformation-environments-guide.md`
    - `scripts/release/day-0-operator-command-pack.sh` (foundation-first sequence)
    - `.agents/plans/2026-03-03-nova-native-cfn-infra-product-reusable-gha-deploy-apis.md`
      (subagent registry + WS11 checklist + verification log)
  - remediation notes:
    - Removed hardcoded region/account prefix list mapping; template now requires
      explicit ingress source selection (`prefix list`, `CIDR`, or `source SG`).
    - Added canonical runtime stack deployment order and change-set-first pattern
      for cross-account reproducibility.
    - Aligned day-0/release runbooks and CLI command-pack variables to the
      runtime-first deployment model.
