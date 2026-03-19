# 2026-03-03 Pre-ECS Release Evidence Log

Status: Historical archive
Owner: Release Architecture + Platform Operations
Last updated: 2026-03-05

This file preserves March 3, 2026 release evidence entries that predate the
current ECS-native blue/green runtime deployment authority. It is retained for
audit traceability only and is non-authoritative for current operations.

Artifact links below may reference `.agents/plans/...` paths. Those files are
local agent working notes and are **not** guaranteed to exist in every clone.

## Archived Entries

- `2026-03-03T08:29:33Z` | operator: `openclaw-project-operator-role` |
  environment: `dev` | gate: `WS4 preflight (A/B/E permissions + role)`
  | result: `BLOCKED`
  - artifact/log links:
    - `.agents/plans/2026-03-03-nova-full-cross-repo-spec-orchestration.md`
      (`0.1` A5 row + `0.3` WS4 blocker evidence)
  - remediation notes:
    - Create Batch-B operator role by applying
      `infra/nova/nova-iam-roles.yml` with `ReleaseValidationTrustedPrincipalArn`
      populated.
    - Grant/read path for:
      `codeconnections:GetConnection`,
      `codepipeline:ListPipelineExecutions`,
      `codepipeline:GetPipelineState`,
      `codedeploy:ListApplications`.
    - Re-run Gate A-E per
      `docs/runbooks/release/nonprod-live-validation-runbook.md`.

- `2026-03-03T09:32:00Z` | operator: `AWSReservedSSO_PowerUserAccess ([REDACTED])` |
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

- `2026-03-03T09:32:00Z` | operator: `AWSReservedSSO_PowerUserAccess ([REDACTED])` |
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
