# Nova operator runbooks

Status: Active
Current repository state: **canonical wave-2 serverless baseline**
Last reviewed: 2026-03-28

## Purpose

Route operators to the surviving release, provisioning, and serverless
operations docs for the canonical repo.

## Active runbooks

- `provisioning/README.md`
- `release/README.md`
- `RUNBOOK-SERVERLESS-OPERATIONS.md`

## Rules

- Active runbooks must describe only the surviving GitHub workflow surface and `infra/nova_cdk`.
- Active runbooks must treat the Regional REST API custom domain as the only
  intended public base URL for the runtime.
- Active runbooks must treat `deploy-output.json` as the published runtime
  authority for the canonical public base URL and deployed release identity.
- Deleted deploy-runtime CloudFormation, ECS worker, and CodePipeline/CodeBuild control-plane paths are not active operator procedures.
- Historical or break-glass material belongs under `docs/history/` if retained for traceability.
