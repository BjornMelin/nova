---
ADR: 0005
Title: Add dedicated nova-auth-api service while keeping local verification default
Status: Accepted
Version: 1.0
Date: 2026-02-12
Related:
  - "[ADR-0001: Deploy on ECS Fargate behind ALB with same-origin routing](./ADR-0001-deployment-on-ecs-fargate-behind-alb.md)"
  - "[ADR-0004: Adopt oidc-jwt-verifier as the canonical JWT/OIDC verification engine](./ADR-0004-canonical-oidc-jwt-verifier-adoption.md)"
  - "[SPEC-0007: Auth API contract](../spec/SPEC-0007-auth-api-contract.md)"
References:
  - "[RFC 7662 OAuth Token Introspection](https://www.rfc-editor.org/rfc/rfc7662)"
  - "[AWS ECS health checks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/load-balancer-healthcheck.html)"
  - "[AWS ALB request tracing](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-request-tracing.html)"
---

## Summary

Add a dedicated `nova-auth-api` service track for shared token verification/introspection use cases, while keeping local JWT verification in `nova-file-api` as the default path.

## Context

Multiple APIs need consistent principal mapping and token policy handling. Centralizing all verification in a remote auth service would increase coupling and availability risk for upload/download control-plane calls.

A balanced architecture is needed:

- local verification by default for resilience and lower latency
- optional remote auth service mode for centralized policy and shared integrations

## Alternatives

- A: Keep auth verification only inside each service.
- B: Make all services depend on remote auth API only.
- C: Add dedicated auth API track, but keep local verification default.

## Decision Framework

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| A | 8.5 | 8.0 | 8.0 | 7.0 | 8.08 |
| B | 6.0 | 7.0 | 5.5 | 8.5 | 6.57 |
| **C** | **9.0** | **9.5** | **8.5** | **10.0** | **9.08** |

`weighted total = (leverage * 0.35) + (value * 0.30) + (maintenance * 0.25) + (adaptability * 0.10)`

## Decision

Choose option C: add `nova-auth-api` as a dedicated service track and keep local verification as default in `nova-file-api`.

Implementation commitments:

- Define `nova-auth-api` contract (`/v1/token/verify`, `/v1/token/introspect`, `/healthz`).
- Preserve local verification path in file-transfer API for fail-safe operations.
- Support optional remote-auth mode through explicit configuration flags.

## Related Requirements

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [IR-0003](../requirements.md#ir-0003-optional-remote-auth-service)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
- [NFR-0003](../requirements.md#nfr-0003-operability)

## Consequences

1. Shared auth use cases gain a dedicated service boundary and independent lifecycle.
2. File-transfer control plane remains resilient during auth service incidents.
3. Operational complexity increases (new repo/deployment), requiring stronger CI/CD and observability gates.

## Changelog

- 2026-02-12 (v1.0): Initial acceptance.
