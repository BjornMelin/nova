---
Spec: 0009
Title: Caching and Idempotency
Status: Active
Version: 1.0
Date: 2026-02-12
Related:
  - "[ADR-0007: Two-tier cache and idempotency store](../adr/ADR-0007-two-tier-cache-and-idempotency-store.md)"
  - "[SPEC-0006: JWT/OIDC verification and principal mapping](./SPEC-0006-jwt-oidc-verification-and-principal-mapping.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
References:
  - "[ElastiCache best practices](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/BestPractices.html)"
---

## 1. Two-tier cache architecture

- Tier 1: local in-process TTL cache
- Tier 2: shared Redis cache (optional)

Read path: local first, then shared cache fallback.
Write path: local + shared cache best effort.

## 2. Primary cache use cases

- JWT verification result caching
- Auth metadata hot-path caching
- Idempotency replay entry storage

## 3. Resilience behavior

- Shared Redis failures MUST not fail request processing by default.
- Cache behavior MUST degrade to local-only mode when shared cache is
  unavailable.
- Readiness should surface shared cache health for operators.

## 4. Idempotency policy

For protected mutation endpoints:

- Require `Idempotency-Key` when feature is enabled.
- Bind replay records to route + caller scope + key.
- Reject key reuse with different payload (`idempotency_conflict`).

## 5. Traceability

- [FR-0004](../requirements.md#fr-0004-idempotency-for-mutation-entrypoints)
- [FR-0006](../requirements.md#fr-0006-two-tier-caching)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
