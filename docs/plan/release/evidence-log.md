# Release Evidence Log

Status: Active
Owner: Release Architecture + Platform Operations
Last updated: 2026-03-05

This file is the canonical active location for live validation and release
promotion evidence links.

Historical pre-ECS March 3, 2026 evidence entries were archived to:

- `../../history/2026-03-v1-hard-cut/release/evidence-log-2026-03-03-pre-ecs.md`

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
    - `/tmp/nova-dev-route-validation.json`
    - `/tmp/nova-prod-route-validation.json`
    - `/tmp/nova-browser-evidence/` (`dev-live.png`, `prod-live.png`, `dev-legacy.png`)
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
