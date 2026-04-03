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

- Active runbooks must describe the surviving human GitHub release-prep flow, the AWS-native release control plane, and `infra/nova_cdk`.
- Active runbooks must describe production WAF as default-on and non-production WAF as opt-in when ingress cost or simplicity is the priority.
- Active runbooks must treat `release/RELEASE-PREP.json` and
  `release/RELEASE-VERSION-MANIFEST.md` as machine-owned release metadata,
  not as narrative documentation.
- Active runbooks must treat the Regional REST API custom domain as the only
  intended public base URL for the runtime.
- Active runbooks must treat `deploy-output.json` as the published runtime
  authority for the canonical public base URL and deployed release identity.
- Deleted ECS worker and legacy deploy-runtime CloudFormation paths are not active operator procedures.
- Historical or break-glass material belongs under `docs/history/` if retained for traceability.
