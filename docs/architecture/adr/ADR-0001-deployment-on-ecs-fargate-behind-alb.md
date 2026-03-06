---
ADR: 0001
Title: Deploy on ECS Fargate behind ALB with same-origin routing
Status: Accepted (partially superseded by ADR-0015, ADR-0023, and ADR-0030)
Version: 1.3
Date: 2026-03-05
Related:
  - "[ADR-0000: Implement the File Transfer API as a FastAPI service](./ADR-0000-fastapi-microservice.md)"
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
References:
  - "[AWS Fargate on ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)"
  - "[ECS container health checks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/healthcheck.html)"
  - "[ALB target group health checks](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/target-group-health-checks.html)"
---

## Summary

Deploy the API as an ECS/Fargate service behind the existing ALB and route
canonical `/v1/transfers/*` and `/v1/jobs/*` traffic to it. Keep browser
traffic same-origin with the parent application to avoid CORS/auth integration
complexity.

Supersession note (2026-03-05): this ADR remains the background decision for
same-origin ALB routing, but deployment platform authority is now centered on
`ADR-0015`, `ADR-0023`, and `ADR-0030`.

## Context

Nova standardizes ECS/Fargate service deployment, ALB path routing, task roles,
and environment injection. This service should follow the same pattern for:

- predictable operations across environments,
- shared ingress and TLS posture,
- minimal frontend integration overhead.

The system must satisfy both health checks and same-origin browser
consumption.

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

- Route `/v1/transfers/*` and `/v1/jobs/*` through the shared ALB.
- Expose health endpoints compatible with ECS/ALB health-check expectations.
- Preserve same-origin access patterns for browser clients.

## Related Requirements

- [FR-0000](../requirements.md#fr-0000-file-transfer-control-plane-endpoints)
- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [NFR-0003](../requirements.md#nfr-0003-operability)
- [IR-0000](../requirements.md#ir-0000-nova-local-runtime-and-release-authority)
- [IR-0001](../requirements.md#ir-0001-sidecar-routing-model)

## Consequences

1. Browser clients avoid CORS preflight and token propagation complexity by remaining
   on one origin.
2. The API can scale independently from frontend services while using common ingress.
3. Path-routing and health-check compatibility become deployment gates for every
   environment rollout.

## Changelog

- 2026-03-03: Aligned route-surface references with `ADR-0023` canonical
  `/v1/*` namespace.
- 2026-02-11: Expanded ADR with deployment constraints, health-check compatibility,
  and restored container-craft context.
- 2026-02-11: Initial ADR accepted.
