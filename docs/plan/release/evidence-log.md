# Release Evidence Log

Status: Active
Owner: Release Architecture + Platform Operations
Last updated: 2026-03-05

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

- `2026-03-05T03:08:06Z` | operator: `AWSReservedSSO_AdministratorAccess (bjorn-dev)` |
  environment: `dev/prod` | gate: `live runtime + route-authority closure`
  | result: `PASS`
  - artifact/log links:
    - `.agents/plans/2026-03-03-nova-iac-closure-dash-pca-hard-cut-integration.md`
      (`Blocker Resolution` + `Verification Evidence` sections)
    - `s3://nova-release-evidence/2026-03-05-live-runtime-route-authority/nova-dev-route-validation.json`
    - `s3://nova-release-evidence/2026-03-05-live-runtime-route-authority/nova-prod-route-validation.json`
    - `s3://nova-release-evidence/2026-03-05-live-runtime-route-authority/nova-browser-evidence.json`
      (`dev-live.png`, `prod-live.png`, `dev-legacy.png`)
  - remediation notes:
    - `nova-file-api-{dev,prod}-runtime-{ecr,cluster,service}` reached
      `CREATE_COMPLETE` in `us-east-1`.
    - Route contract passed for both environments:
      canonical health routes `200`, legacy route probes `404`.

- `2026-03-05T03:15:00Z` | operator: `AWSReservedSSO_AdministratorAccess (bjorn-dev)` |
  environment: `dev/prod` | gate: `SSM base-url authority reconciliation`
  | result: `PASS`
  - artifact/log links:
    - `.agents/agent-memory/2026-03-04-orchestrator-nova-iac-dash-hard-cut.md`
      (`Orchestrator Final Reconciliation - 2026-03-05T03:15:00Z`)
  - remediation notes:
    - Detected drift where `nova-ci-{dev,prod}-service-base-url` reported
      `AWS::SSM::Parameter` resource `DELETED`.
    - Recovered by deleting/recreating canonical marker stacks and verifying:
      - `/nova/dev/nova-file-api/base-url`
      - `/nova/prod/nova-file-api/base-url`
      - `/nova/dev/nova-file-api/image-digest`
      - `/nova/prod/nova-file-api/image-digest`
