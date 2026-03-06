---
Spec: 0009
Title: Caching and Idempotency
Status: Active
Version: 1.3
Date: 2026-03-05
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
- Tier 2: shared Redis cache

Read path: local first, then shared cache fallback.
Write path: local + shared cache best effort.

Shared keys are namespaced and schema-versioned (`CACHE_KEY_PREFIX`,
`CACHE_KEY_SCHEMA_VERSION`) to support safe key evolution and cutover.

## 2. Primary cache use cases

- JWT verification result caching
- Auth metadata hot-path caching
- Idempotency replay entry storage, with explicit mode selection

JWT cache entries MUST use TTL derived from token expiration (`exp`) with
configured upper bounds.

## 3. Resilience behavior

- Shared Redis failures MAY remain best-effort for non-critical read caching.
- `IDEMPOTENCY_MODE=shared_required` makes the shared cache traffic-critical for
  mutation claims and readiness.
- `IDEMPOTENCY_MODE=local_only` is limited to explicit local/single-process
  operation and must not be treated as the production default for AWS-backed
  multi-instance deployments.

## 4. Idempotency policy

For protected mutation endpoints:

- Require `Idempotency-Key` when feature is enabled.
- Support explicit runtime modes:
  - `shared_required` for distributed correctness
  - `local_only` for explicit local/single-process operation
- Bind replay records to route + caller scope + key.
- Reject key reuse with different payload (`idempotency_conflict`).
- Use explicit record state transitions:
  - `in_progress` claim before execution
  - `committed` after success response
  - claim discard on failure path
- `shared_required` mode requires `CACHE_REDIS_URL` and must fail mutations with
  `503` (`error.code = "idempotency_unavailable"`) when the distributed claim
  store cannot be used safely.
- Enqueue failures (`503` + `error.code = "queue_unavailable"`) MUST NOT be
  replay-cached as successful responses.

## 5. Traceability

- [FR-0004](../requirements.md#fr-0004-idempotency-for-mutation-entrypoints)
- [FR-0006](../requirements.md#fr-0006-two-tier-caching)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)

## Changelog

- 2026-03-05 (v1.3): Added explicit idempotency modes, made shared-cache-backed
  idempotency traffic-critical in production, and documented
  `503 idempotency_unavailable` failure semantics.
