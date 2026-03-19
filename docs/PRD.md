# Product Requirements Document (PRD): Nova Runtime

Status: Active canonical PRD
Last updated: 2026-03-19
Audience: Product, Engineering, Platform Operations

## 1. Product Goal

Deliver one production-ready API control-plane contract for file transfer and
async jobs with zero route-surface ambiguity, **one public runtime** for JWT
verification, and **claim-derived** caller scope (no parallel session/header
auth channel).

## 2. Desired Outcomes

- One canonical public URL namespace: `/v1/*` (plus `/metrics/summary`).
- Public **contract revision** for auth and OpenAPI expression under
  `SPEC-0027` without introducing a `/v2/*` prefix unless a future ADR does so
  explicitly.
- Zero active references to non-canonical route literals in runtime and active
  operator docs.
- One truthful active operator authority graph across runtime API, SDK, and
  deploy-validation governance, including the
  [green-field program](./plan/greenfield-simplification-program.md) and
  `ADR-0033`–`ADR-0041` / `SPEC-0027`–`SPEC-0029`.
- One generated runtime-config matrix for deploy/docs/test consumers, backed by
  the typed settings model rather than duplicated env-key lists.
- Superseded ADR/SPEC material is quarantined outside the active authority set
  (including superseded `ADR-0005` and `SPEC-0007`).
- Stable generated-client and conformance behavior against current OpenAPI.
- Ergonomic SDK-facing OpenAPI identifiers and semantic generator groupings
  remain stable across regeneration.
- TypeScript SDKs use `openapi-typescript` + `openapi-fetch` per `ADR-0038` /
  `SPEC-0029` while honoring active `SPEC-0012` (predecessor package-map detail,
  if needed for archaeology only:
  [`spec/index.md`](./architecture/spec/index.md) → Superseded `SPEC-0011`).
- Worker job completion uses **direct persistence**, not an internal HTTP
  callback (`SPEC-0028`, `ADR-0035`).
- Release promotion evidence is complete for non-prod validation and dev→prod
  promotion controls.

## 3. Product Requirements

1. Runtime capabilities remain available for transfer orchestration, async job
   control plane, capability/release discovery, health/readiness, and metrics.
2. Runtime semantics preserve queue failure behavior (`503 queue_unavailable`),
   aggregate readiness contract (including bucket and OIDC failure checks),
   two-tier idempotency behavior, and worker terminal-state normalization
   (`succeeded` clears `error`).
3. OpenAPI 3.1 output remains the contract source for SDK/client generation and
   policy checks, with native FastAPI expression preferred (`ADR-0036`),
   stable snake_case `operationId` values, semantic SDK grouping tags, and
   resolvable named component schemas for custom request bodies.
4. Release policy enforces immutable artifact promotion and auditable manual
   approval before prod.
5. Documentation authority remains singular and unambiguous across README,
   PRD, requirements, ADR/SPEC, plan, and runbooks, synchronized per
   `SPEC-0020` (including green-field branch merge policy).
6. Public SDK productization follows `ADR-0038`, `SPEC-0029`, and `SPEC-0012`
   (Python public; TypeScript CodeArtifact staged/prod; R internal first-class
   line). Superseded predecessors (`ADR-0013`, `SPEC-0011`, etc.) are listed only
   in [`adr/index.md`](./architecture/adr/index.md) and
   [`spec/index.md`](./architecture/spec/index.md) (Superseded tables) and under
   `adr/superseded/` / `spec/superseded/`—not active authority.
7. Deployment target-state aligns with `ADR-0015` / `ADR-0039`: ECS/Fargate
   behind ALB (and CloudFront/WAF ingress as described in platform docs),
   ECS-native blue/green rollout, CloudWatch alarms, WAF on public ingress, and
   manifest hash evidence tied to the release manifest.
8. `nova_dash_bridge` remains an adapter-only integration surface and consumes
   canonical in-process transfer contracts through `nova_file_api.public`
   (async-first target per `ADR-0037`).
9. Runtime deploy/operator surfaces must share one generated env/override
   contract derived from the typed runtime settings plus minimal curated
   template metadata.

## 4. Scope and Non-Goals

In scope:

- Canonical `/v1/*` runtime contract stewardship.
- Green-field simplification program execution and documentation
  (`docs/plan/greenfield-simplification-program.md`).
- Async job and transfer orchestration reliability requirements.
- CI/CD and release governance alignment with active Nova docs.

Out of scope:

- Compatibility alias routes for removed namespaces.
- Data-plane byte proxying through FastAPI.
- Re-introducing split/dual authority documentation models.
- A separate auth microservice or dedicated `/v1/token/*` public surface in the
  target architecture.

## 5. Success Metrics

- 100% pass rate for OpenAPI path policy checks enforcing `/v1/*` plus
  `/metrics/summary`.
- 100% pass rate for generated-client smoke against current OpenAPI schema.
- 100% pass rate for route guard checks against disallowed legacy literals.
- Non-prod validation evidence covers canonical route behavior and required
  release gates.

## 6. Acceptance Criteria

1. Active docs reference the canonical chain including `ADR-0023`,
   `SPEC-0000`, `SPEC-0016`, `requirements.md`, and the green-field overlays
   `SPEC-0027`–`SPEC-0029` / `ADR-0033`–`ADR-0041` where relevant.
2. Active plan/runbook docs reference
   `docs/plan/greenfield-simplification-program.md` when scope touches the
   program.
3. Historical artifacts are discoverable only through history indexes,
   archive paths, or the dedicated superseded ADR/SPEC directories.
4. Contract and release docs stay synchronized in the same change set as
   behavioral changes (`SPEC-0020`).
5. Downstream integration contracts, Auth0 workflow contracts, and SSM base URL
   authority contracts remain aligned with active ADR/SPEC and test guardrails.
6. Auth0 tenant import/export paths are fail-fast and cannot mutate tenants when
   contract validation fails.
7. CodeArtifact promotion IAM contracts remain least-privilege, scoped to
   explicit staged source and prod destination repositories, and cover Python
   distributions, TypeScript staged/prod package promotion, and R generic
   package artifacts.
8. Active operator authority IDs and paths are truthful, resolvable, and
   synchronized across README, AGENTS, plan, PRD, runbooks, and architecture
   indexes.
9. Superseded ADR/SPEC content is excluded from active authority lists and
   active index sections.

## 7. Risks

- Consumer drift to retired routes if downstream defaults regress.
- Documentation drift if active files duplicate route or release authority.
- Runtime config drift if deploy scripts, templates, tests, and docs carry
  separate handwritten env/override lists.
- Guardrail erosion if CI checks are renamed/removed without doc updates.
- Temporary mismatch between target authority docs and in-flight code during
  green-field execution if branches land without synchronized doc updates.

## 8. Active References

- `docs/architecture/requirements.md`
- `docs/plan/greenfield-simplification-program.md`
- `docs/plan/greenfield-authority-map.md`
- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `docs/architecture/adr/ADR-0024-layered-architecture-authority-pack.md`
- `docs/architecture/adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md`
- `docs/architecture/adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md`
- `docs/architecture/adr/ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md`
- `docs/architecture/adr/ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md`
- `docs/architecture/adr/ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md`
- `docs/architecture/adr/ADR-0033-single-runtime-auth-authority.md`
- `docs/architecture/adr/ADR-0034-bearer-jwt-public-auth-contract.md`
- `docs/architecture/adr/ADR-0035-worker-direct-result-persistence.md`
- `docs/architecture/adr/ADR-0036-native-fastapi-openapi-contract.md`
- `docs/architecture/adr/ADR-0041-shared-pure-asgi-middleware-and-errors.md`
- `docs/architecture/adr/ADR-0037-async-first-public-surface.md`
- `docs/architecture/adr/ADR-0038-sdk-architecture-by-language.md`
- `docs/architecture/adr/ADR-0039-aws-target-platform.md`
- `docs/architecture/adr/ADR-0040-repo-rebaseline-after-cuts.md`
- `docs/architecture/spec/SPEC-0000-http-api-contract.md`
- `docs/architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md`
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `docs/architecture/spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md`
- `docs/architecture/spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md`
- `docs/architecture/spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md`
- `docs/architecture/spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md`
- `docs/architecture/spec/SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md`
- `docs/architecture/spec/SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md`
- `docs/architecture/spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md`
- `docs/architecture/spec/SPEC-0027-public-http-contract-revision-and-bearer-auth.md`
- `docs/architecture/spec/SPEC-0028-worker-job-lifecycle-and-direct-result-path.md`
- `docs/architecture/spec/SPEC-0029-sdk-architecture-and-artifact-contract.md`
- `docs/standards/README.md`
- `docs/plan/PLAN.md`
- `docs/runbooks/README.md`
