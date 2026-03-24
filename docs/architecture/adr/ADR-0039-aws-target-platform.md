---
ADR: 0039
Title: Green-field AWS target platform
Status: Accepted
Version: 1.0
Date: 2026-03-19
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API contract](../spec/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[ADR-0015: Nova API platform final hosting and deployment architecture (2026)](./ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md)"
  - "[SPEC-0015: Nova API platform final topology and delivery contract](../spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md)"
  - "[ADR-0001: Deploy on ECS Fargate behind ALB](./ADR-0001-deployment-on-ecs-fargate-behind-alb.md)"
  - "[Green-field simplification program](../../plan/greenfield-simplification-program.md)"
References:
  - "[TARGET_ARCHITECTURE (pack)](../../../.agents/nova_greenfield_codex_pack/TARGET_ARCHITECTURE.md)"
---

## Summary

Nova’s target platform is **CloudFront (+ WAF) → internal ALB → ECS/Fargate**
for **API and worker** services, with **S3**, **SQS**, **DynamoDB**, secrets/config via
**Secrets Manager / SSM**, and **ADOT/OpenTelemetry**-style observability. **JWT
verification stays in-app.** Composite end-to-end architecture scores
**9.23/10**; DynamoDB scores **9.31/10** under Framework C (see
[green-field evidence](../../plan/greenfield-evidence/DECISION_FRAMEWORKS_AND_SCORES.md)).

## Context

- Steady HTTP API **plus** long-running worker, not only bursty traffic.
- Managed services and low operational burden are preferred
  ([GFR-R7](../requirements.md#gfr-r7--managed-aws-services-preferred)).
- This ADR **aligns** [ADR-0015](./ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md)
  narrative with the green-field composite scoring narrative; it does not
  replace deploy-governance authority ([ADR-0030](./ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md)–[ADR-0032](./ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)).
- Execution order: program branch 10.

## Decision

**Accept** the composite **CloudFront (+ WAF) → internal ALB → ECS/Fargate** platform
with **S3**, **SQS**, **DynamoDB**, standard secrets/config, and
ADOT-oriented observability, with **separate** API and worker ECS services.
**DynamoDB** remains the primary metadata/activity store pattern. **JWT
verification remains application-authoritative**; ALB JWT is optional
defense-in-depth only and is not the primary auth contract.

## Implementation commitments

- Implement infra and runtime config consistent with the topology described in
  `.agents/nova_greenfield_codex_pack/TARGET_ARCHITECTURE.md` and
  [SPEC-0015](../spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md).
- Branch `infra/greenfield-ecs-platform`.

## Related requirements

- [GFR-R7](../requirements.md#gfr-r7--managed-aws-services-preferred)

## Consequences

1. **Positive:** CloudFront edge controls plus ECS blue/green patterns, shared
   images between API and worker, managed data plane for jobs/activity.
2. **Trade-offs:** AWS lock-in trade-offs accepted; ECS operations remain
   non-trivial.
3. **Ongoing:** Cost and capacity reviews; optional API Gateway or edge auth only
   via future ADRs.

## Changelog

- 2026-03-19: Canonical ADR ported from green-field pack ADR-0007; fixed
  evidence link to pack `TARGET_ARCHITECTURE` via repo-relative path in program
  docs.
