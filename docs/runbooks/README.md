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

## Authority / references

- [requirements.md](../architecture/requirements.md) -- green-field baseline
  requirements that drive operator contracts.
- [ADR-0023 hard-cut v1 route surface](../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md) -- canonical API/ops route constraints for V1.
- [SPEC-0016 V1 route namespace and literal guardrails](../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md) -- route namespace and route-pattern guardrails.
- [SPEC-0027 Public API v2](../architecture/spec/SPEC-0027-public-api-v2.md) -- primary public API and ops contract baseline.
- [Green-field execution runbook](../plan/GREENFIELD-WAVE-2-EXECUTION.md) -- active green-field rollout execution plan used by this runbooks cluster.
- ADR-0033 chain: [ADR-0033](../architecture/adr/ADR-0033-canonical-serverless-platform.md), [ADR-0034](../architecture/adr/ADR-0034-eliminate-auth-service-and-session-auth.md), [ADR-0035](../architecture/adr/ADR-0035-replace-generic-jobs-with-export-workflows.md), [ADR-0036](../architecture/adr/ADR-0036-dynamodb-idempotency-no-redis.md), [ADR-0037](../architecture/adr/ADR-0037-sdk-generation-consolidation.md), [ADR-0038](../architecture/adr/ADR-0038-docs-authority-reset.md) -- green-field overlay ADR chain.
- SPEC-0027/31 chain: [SPEC-0027](../architecture/spec/SPEC-0027-public-api-v2.md), [SPEC-0028](../architecture/spec/SPEC-0028-export-workflow-state-machine.md), [SPEC-0029](../architecture/spec/SPEC-0029-platform-serverless.md), [SPEC-0030](../architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md), [SPEC-0031](../architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md) -- green-field overlay specs for API, workflow, platform, SDK, and docs/test authority reset.
