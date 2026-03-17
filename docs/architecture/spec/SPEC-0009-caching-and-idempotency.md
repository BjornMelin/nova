---
Spec: 0009
Title: Caching and Idempotency
Status: Active
Version: 1.3
Date: 2026-03-16
Related:
  - "[ADR-0007: Two-tier cache and idempotency store](../adr/ADR-0007-two-tier-cache-and-idempotency-store.md)"
  - "[SPEC-0006: JWT/OIDC verification and principal mapping](./SPEC-0006-jwt-oidc-verification-and-principal-mapping.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
References:
  - "[ElastiCache best practices](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/BestPractices.html)"
  - "[redis-py asyncio examples](https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html)"
  - "[redis-py retry helpers](https://redis.readthedocs.io/en/stable/retry.html)"
---

## 1. Two-tier cache architecture

- Tier 1: local in-process TTL cache
- Tier 2: shared Redis cache (optional)

Read path: local first, then shared cache fallback.
Write path: local + shared cache best effort.

Shared keys are namespaced and schema-versioned (`CACHE_KEY_PREFIX`,
`CACHE_KEY_SCHEMA_VERSION`) to support safe key evolution and cutover.

## 2. Primary cache use cases

- JWT verification result caching
- Auth metadata hot-path caching
- Shared Redis-backed idempotency claim and replay storage

JWT cache entries MUST use TTL derived from token expiration (`exp`) with
configured upper bounds.

## 3. Resilience behavior

- Shared Redis failures MUST not fail request processing by default.
- General cache behavior MAY degrade to local-only operation when the shared
  cache is unavailable.
- Mutation idempotency correctness MUST NOT degrade to local-only claim
  handling when idempotency is enabled.
- Readiness should surface shared cache health for operators.

## 4. Idempotency policy

For protected mutation endpoints:

- `IDEMPOTENCY_ENABLED=true` requires `CACHE_REDIS_URL`.
- Missing `Idempotency-Key` is allowed; blank keys are invalid.
- Bind replay records to route + caller scope + key.
- Reject key reuse with different payload (`idempotency_conflict`).
- Use explicit record state transitions:
  - `in_progress` claim before execution
  - `committed` after success response
  - claim discard on failure path
- Shared idempotency-store failures MUST fail closed with `503` and
  `error.code = "idempotency_unavailable"`.
- Enqueue failures (`503` + `error.code = "queue_unavailable"`) MUST NOT be
  replay-cached as successful responses.

## 5. Traceability

- [FR-0004](../requirements.md#fr-0004-idempotency-for-mutation-entrypoints)
- [FR-0006](../requirements.md#fr-0006-two-tier-caching)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
