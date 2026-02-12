---
ADR: 0007
Title: Adopt two-tier cache with idempotency replay storage
Status: Accepted
Version: 1.0
Date: 2026-02-12
Related:
  - "[SPEC-0009: Caching and idempotency](../spec/SPEC-0009-caching-and-idempotency.md)"
  - "[SPEC-0006: JWT/OIDC verification and principal mapping](../spec/SPEC-0006-jwt-oidc-verification-and-principal-mapping.md)"
References:
  - "[ElastiCache best practices](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/BestPractices.html)"
  - "[RFC 7231](https://datatracker.ietf.org/doc/html/rfc7231)"
---

## Summary

Adopt a two-tier cache model (local TTL + shared Redis) and use it for auth hot
paths and idempotent replay records.

## Context

The API needs low-latency repeated reads for token verification artifacts and
safe retry handling for mutation endpoints. Pure local cache does not scale
across instances. Pure remote cache adds avoidable dependency risk.

## Alternatives

- A: Local cache only
- B: Redis only
- C: Two-tier local + Redis

## Decision Framework

| Option | Solution leverage (35%) | Application value (30%) | Maintenance and cognitive load (25%) | Architectural adaptability (10%) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| A | 6.5 | 6.5 | 8.5 | 5.5 | 6.88 |
| B | 8.0 | 8.5 | 6.5 | 8.5 | 7.75 |
| **C** | **9.5** | **9.0** | **8.5** | **9.0** | **9.00** |

## Decision

Choose option C.

Implementation commitments:

- Local in-memory TTL cache for fastest-path reads.
- Optional shared Redis cache for cross-instance consistency.
- Degrade gracefully to local-only mode when Redis is unavailable.
- Store `Idempotency-Key` replay records with payload hash validation.

## Consequences

1. Better latency and resilience than single-layer approaches.
2. Safe client retries without duplicate side effects on key mutation routes.
3. Additional operational dependency (Redis) in production AWS deployments.

## Change Log

- 2026-02-12 (v1.0): Initial acceptance.
