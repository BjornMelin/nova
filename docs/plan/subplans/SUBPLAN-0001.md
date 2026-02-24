# SUBPLAN-0001

- Branch name: `feat/subplan-0001-core-runtime-contract-hardening`

## Core Runtime + Contract Hardening

Order: 1 of 5
Parent plan: `docs/plan/PLAN.md`

## Persona

Staff FastAPI API Engineer (contract-first, security-focused, anti-overengineering)

## Objective

Deliver the production-ready core runtime for file-transfer control-plane,
including contract-stable endpoints, auth mode support, idempotency on entry
mutations, and baseline tests.

## Scope

Repository scope (this monorepo):

- `apps/nova_file_api_service`
- `apps/nova_auth_api_service`
- `packages/nova_file_api`
- `packages/nova_auth_api`
- `packages/contracts`

In scope:

- FastAPI app/router/runtime wiring
- Request/response models and error envelope
- Transfer control-plane service surface
- Auth mode boundaries (same-origin, local JWT, optional remote auth)
- Idempotency support for initiate/enqueue
- Health/readiness/metrics endpoints

Out of scope:

- Full infra rollout changes in `container-craft`
- Cross-repo migration execution

## Mandatory Research Inputs

- FastAPI lifespan: <https://fastapi.tiangolo.com/advanced/events/>
- FastAPI worker model: <https://fastapi.tiangolo.com/deployment/server-workers/>
- Starlette threadpool: <https://www.starlette.io/threadpool/>
- AnyIO threads: <https://anyio.readthedocs.io/en/latest/threads.html>
- FastAPI best practices: <https://github.com/zhanymkanov/fastapi-best-practices>
- RFC 6750: <https://datatracker.ietf.org/doc/html/rfc6750>

## Checklist

### A. API and contract

- [x] Implement transfer endpoints under `/api/transfers/*` and `/api/jobs/*`
- [x] Implement standard error envelope and request-id propagation
- [x] Keep OpenAPI generation enabled and contract-aligned

### B. Auth and security

- [x] Add same-origin and JWT auth modes
- [x] Use `oidc-jwt-verifier` for local JWT mode
- [x] Run sync JWT verification behind threadpool boundary
- [x] Keep optional remote auth mode fail-closed

### C. Idempotency

- [x] Require `Idempotency-Key` on initiate/enqueue when enabled
- [x] Replay same-key/same-payload responses
- [x] Reject key reuse with different payload (`idempotency_conflict`)

### D. Tests and gates

- [x] Add endpoint tests for health/readiness and idempotency behavior
- [x] Keep readiness checks scoped to critical dependencies (not feature flags)
- [x] Pass ruff/mypy/pytest quality gates

## Acceptance Criteria

- Contract endpoints are implemented and reachable.
- Error envelope shape is stable.
- Auth and idempotency behavior are enforced as specified.
- Quality gates pass.
