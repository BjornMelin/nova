# Product Requirements Document (PRD): Nova Runtime

Status: Active canonical PRD
Last updated: 2026-03-03
Audience: Product, Engineering, Platform Operations

## 1. Product Goal

Deliver one production-ready API control-plane contract for file transfer and
async jobs with zero route-surface ambiguity.

## 2. Desired Outcomes

- One canonical public namespace: `/v1/*` (plus `/metrics/summary`).
- Zero active references to removed route families (`/api/*`, `/api/v1/*`,
  `/healthz`, `/readyz`) in runtime and active operator docs.
- Stable generated-client and conformance behavior against current OpenAPI.
- Release promotion evidence is complete for non-prod validation and dev->prod
  promotion controls.

## 3. Product Requirements

1. Runtime capabilities remain available for transfer orchestration, async job
   control plane, capability/release discovery, health/readiness, and metrics.
2. Runtime semantics preserve queue failure behavior (`503 queue_unavailable`),
   readiness dependency-scoping, and worker update normalization.
3. OpenAPI 3.1 output remains the contract source for SDK/client generation and
   policy checks.
4. Release policy enforces immutable artifact promotion and auditable manual
   approval before prod.
5. Documentation authority remains singular and unambiguous across README,
   PRD, requirements, ADR/SPEC, plan, and runbooks.

## 4. Scope and Non-Goals

In scope:

- Canonical `/v1/*` runtime contract stewardship.
- Async job and transfer orchestration reliability requirements.
- CI/CD and release governance alignment with active Nova docs.

Out of scope:

- Compatibility alias routes for removed namespaces.
- Data-plane byte proxying through FastAPI.
- Re-introducing split/dual authority documentation models.

## 5. Success Metrics

- 100% pass rate for OpenAPI path policy checks enforcing `/v1/*` plus
  `/metrics/summary`.
- 100% pass rate for generated-client smoke against current OpenAPI schema.
- 100% pass rate for route guard checks against disallowed legacy literals.
- Non-prod validation evidence covers canonical route behavior and required
  release gates.

## 6. Acceptance Criteria

1. Active docs reference a single authority chain:
   `ADR-0023` + `SPEC-0000` + `SPEC-0016` + `requirements.md`.
2. Active plan/runbook docs no longer depend on archived subplan/trigger stubs.
3. Historical artifacts are discoverable only through history indexes and
   archive paths.
4. Contract and release docs stay synchronized in the same change set.

## 7. Risks

- Consumer drift to retired routes if downstream defaults regress.
- Documentation drift if active files duplicate route or release authority.
- Guardrail erosion if CI checks are renamed/removed without doc updates.

## 8. Active References

- `docs/architecture/requirements.md`
- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `docs/architecture/spec/SPEC-0000-http-api-contract.md`
- `docs/architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md`
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `docs/plan/PLAN.md`
- `docs/runbooks/README.md`
