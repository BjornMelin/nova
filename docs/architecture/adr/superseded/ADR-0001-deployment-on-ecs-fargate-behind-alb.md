---
ADR: 0001
Title: Deploy on ECS Fargate behind ALB
Status: Superseded
Superseded-by: "[ADR-0033: Canonical serverless platform](../ADR-0033-canonical-serverless-platform.md)"
Version: 1.3
Date: 2026-03-05
Related:
  - "[ADR-0000: Implement the File Transfer API as a FastAPI service](../ADR-0000-fastapi-microservice.md)"
  - "[ADR-0015: Nova API platform final hosting and deployment architecture (2026)](./ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md)"
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](../ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[ADR-0030: Native-CFN modular stack architecture for Nova infrastructure productization](../ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md)"
References:
  - "[AWS Fargate on ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)"
  - "[ECS container health checks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/healthcheck.html)"
  - "[ALB target group health checks](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/target-group-health-checks.html)"
---

> Historical traceability note: this ECS/ALB placement decision is preserved for
> lineage only. The active ingress/runtime baseline is the serverless platform
> defined in `ADR-0033` and `SPEC-0029`.

## Summary

Deploy the API as an ECS/Fargate service behind an ALB and route canonical
`/v1/transfers/*` and `/v1/jobs/*` traffic to it. This ADR captures the service
placement decision; the current public ingress posture is now partially
superseded by the regional REST API ingress described in `ADR-0033` and
`SPEC-0029`.

## Context

Nova standardizes ECS/Fargate service deployment, ALB-backed service ingress,
task roles, and environment injection. This service should follow the same
pattern for:

- predictable operations across environments,
- shared ingress and TLS posture,
- minimal frontend integration overhead.

The system must satisfy health-check compatibility and stable ingress into the
Nova runtime service.

## Alternatives

- A: ECS/Fargate service behind shared ALB with path-based routing.
- B: API Gateway + Lambda control plane.
- C: Separate domain/ALB for the API with cross-origin browser calls.

## Decision Framework

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| **A** | **10** | **9** | **9** | **9** | **9.35** |
| B | 7 | 7 | 7 | 8 | 7.20 |
| C | 6 | 7 | 6 | 7 | 6.40 |

## Decision

Choose option A.

Implementation commitments:

- Route `/v1/transfers/*` and `/v1/jobs/*` through the ALB-backed runtime
  service path.
- Expose health endpoints compatible with ECS/ALB health-check expectations.
- Preserve a browser-compatible ingress path while allowing later edge
  hardening above the ALB layer.

## Related Requirements

- [FR-0000](../requirements.md#fr-0000-file-transfer-control-plane-endpoints)
- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [NFR-0003](../requirements.md#nfr-0003-operability)
- [IR-0000](../requirements.md#ir-0000-nova-local-runtime-and-release-authority)
- [IR-0001](../requirements.md#ir-0001-sidecar-routing-model)

## Consequences

1. The API can scale independently while retaining ALB-native health checks and
   service routing.
2. Later ingress evolution can replace the public edge without replacing the
   ECS/Fargate service decision captured here.
3. Path-routing and health-check compatibility become deployment gates for every
   environment rollout.

## Changelog

- 2026-03-29: Moved to `adr/superseded/` and marked superseded by the active
  serverless platform baseline.
- 2026-03-03: Aligned route-surface references with `ADR-0023` canonical
  `/v1/*` namespace.
- 2026-03-28: Updated superseding ingress references to the regional REST API
  baseline in `ADR-0033` / `SPEC-0029`.
- 2026-02-11: Expanded ADR with deployment constraints and health-check
  compatibility.
- 2026-02-11: Initial ADR accepted.
