---
ADR: 0004
Title: Adopt oidc-jwt-verifier as the canonical JWT/OIDC verification engine
Status: Accepted
Version: 1.0
Date: 2026-02-12
Related:
  - "[ADR-0000: Implement the File Transfer API as a FastAPI service](./ADR-0000-fastapi-microservice.md)"
  - "[SPEC-0001: Security model](../spec/SPEC-0001-security-model.md)"
  - "[SPEC-0006: JWT/OIDC verification and principal mapping](../spec/SPEC-0006-jwt-oidc-verification-and-principal-mapping.md)"
References:
  - "[oidc-jwt-verifier source](https://github.com/BjornMelin/oidc-jwt-verifier)"
  - "[PyJWT API](https://pyjwt.readthedocs.io/en/latest/api.html)"
  - "[RFC 8725 JWT BCP](https://datatracker.ietf.org/doc/html/rfc8725)"
  - "[Auth0 token validation](https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens)"
---

## Summary

Adopt `oidc-jwt-verifier` as the canonical JWT/OIDC verification core for this program. Provider-specific behavior (including Auth0) is configured through standard OIDC inputs instead of provider-locked verifier implementations.

## Context

The current plan used an Auth0-specific verifier module. This creates provider coupling and duplicates security-critical JWT logic that is already implemented in `oidc-jwt-verifier`.

The existing package provides:

- claim verification for `iss`, `aud`, `exp`, and `nbf`
- explicit algorithm allowlisting
- dangerous header rejection (`jku`, `x5u`, `crit`)
- JWKS retrieval and caching
- stable error semantics with RFC 6750 `WWW-Authenticate` header construction

The package is synchronous. In FastAPI async dependencies, direct sync verification calls create event-loop blocking risk under cache misses/network delays.

## Alternatives

- A: Keep Auth0-specific verifier in `aws-file-api`.
- B: Build custom generic OIDC verifier in `aws-file-api`.
- C: Adopt `oidc-jwt-verifier` as canonical verification engine.

## Decision Framework

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| A | 6.0 | 7.0 | 5.0 | 6.0 | 6.10 |
| B | 7.0 | 8.0 | 6.0 | 8.0 | 7.15 |
| **C** | **10.0** | **9.5** | **9.0** | **9.5** | **9.50** |

`weighted total = (leverage * 0.35) + (value * 0.30) + (maintenance * 0.25) + (adaptability * 0.10)`

## Decision

Choose option C: `oidc-jwt-verifier` is the canonical JWT/OIDC verification engine.

Implementation commitments:

- `aws-file-api` provides `auth/oidc_verifier.py` as adapter layer.
- Auth verification in async dependency path runs through threadpool boundary (`anyio.to_thread.run_sync` or equivalent).
- Auth0 support remains first-class through OIDC config mapping (`issuer`, `audience`, `jwks_url`) without provider-locked verifier classes.

## Related Requirements

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0003](../requirements.md#fr-0003-key-generation-and-scope-enforcement)
- [NFR-0000](../requirements.md#nfr-0000-security-baseline)
- [NFR-0001](../requirements.md#nfr-0001-performance-and-event-loop-safety)

## Consequences

1. Security policy logic is centralized and reused across services.
2. Provider lock-in is reduced; Auth0 remains supported via OIDC configuration.
3. Async integration must enforce non-blocking boundaries to avoid throughput regressions.

## Changelog

- 2026-02-12: Initial ADR accepted.
