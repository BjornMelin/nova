---
Spec: 0009
Title: Caching and Idempotency
Status: Active
Version: 1.3
Date: 2026-03-16
Related:
  - "[ADR-0036: DynamoDB idempotency and transient state, no Redis](../adr/ADR-0036-dynamodb-idempotency-no-redis.md)"
  - "[SPEC-0006: JWT/OIDC verification and principal mapping](./SPEC-0006-jwt-oidc-verification-and-principal-mapping.md)"
  - "[SPEC-0000: HTTP API contract](./superseded/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
References:
  - "[Using time to live (TTL) in DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html)"
  - "[Working with expired items and time to live (TTL)](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/ttl-expired-items.html)"
---

## 1. Cache architecture

- Local in-process TTL cache for correctness-neutral hot paths such as JWT
  verification result caching

Read path: local cache only.
Write path: local cache only.

Cache keys are namespaced and schema-versioned (`CACHE_KEY_PREFIX`,
`CACHE_KEY_SCHEMA_VERSION`) to support safe key evolution and cutover.

## 2. Primary cache use cases

- JWT verification result caching
- Auth metadata hot-path caching

JWT cache entries MUST use TTL derived from token expiration (`exp`) with
configured upper bounds.

## 3. Resilience behavior

- Local cache is an optimization only and MUST NOT be treated as authoritative
  shared state.
- Mutation idempotency correctness MUST NOT degrade to local-only claim
  handling when idempotency is enabled.
- Readiness should surface idempotency-store health for operators.

## 4. Idempotency policy

For protected mutation endpoints:

- DynamoDB-backed idempotency claim and replay storage is correctness state,
  not a cache use case.
- API-runtime `IDEMPOTENCY_ENABLED=true` requires
  `IDEMPOTENCY_DYNAMODB_TABLE`.
- Missing `Idempotency-Key` is allowed; blank keys are invalid.
- Bind replay records to route + caller scope + key.
- Reject key reuse with different payload (`idempotency_conflict`).
- Use explicit record state transitions:
  - `in_progress` claim before execution
  - `committed` after success response
  - claim discard on failure path
- Treat `expires_at` as an application-level validity boundary because DynamoDB
  TTL deletion is eventual.
- Shared idempotency-store failures MUST fail closed with `503` and
  `error.code = "idempotency_unavailable"`.
- If execution succeeds but commit persistence fails, the runtime MUST keep the
  existing `in_progress` claim so retries with the same key do not re-execute
  the mutation.
- Clients receiving `idempotency_unavailable` from a protected mutation MUST
  retry with the same `Idempotency-Key`; rotating keys after this failure mode
  is unsafe because the original mutation may already have applied.
- Enqueue failures (`503` + `error.code = "queue_unavailable"`) MUST NOT be
  replay-cached as successful responses.

## 5. Traceability

- [FR-0004](../requirements.md#fr-0004-idempotency-for-mutation-entrypoints)
- [FR-0006](../requirements.md#fr-0006-two-tier-caching)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
