# SUBPLAN-001: Auth hooks + scope resolution

## Goal

Make scope derivation pluggable and support JWT/OIDC mode.

## Steps

1. Define `AuthPolicy` concept:
   - verifier function
   - scope resolver function
2. Implement JWT verification (OIDC) behind a feature flag.
3. Ensure key scoping uses `scope_id` derived from auth claim.

## Exit criteria

- API rejects unauthenticated requests when auth is required.
- Scope-based key enforcement passes tests.
