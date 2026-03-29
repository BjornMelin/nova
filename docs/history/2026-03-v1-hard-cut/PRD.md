# PRD (Superseded Notice)

> Supersession Notice (2026-02-28)
>
> This document is retained for historical context and is non-authoritative where it conflicts with the finalized consolidation architecture.
>
> Canonical authority:
>
> - docs/architecture/adr/superseded/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md
> - docs/architecture/adr/superseded/ADR-0014-container-craft-capability-absorption-and-repo-retirement.md
> - docs/architecture/adr/superseded/ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md
> - docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md
> - docs/architecture/spec/superseded/SPEC-0011-multi-language-sdk-architecture-and-package-map.md
> - docs/architecture/spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md
> - docs/architecture/spec/superseded/SPEC-0013-container-craft-capability-absorption-execution-spec.md
> - docs/architecture/spec/superseded/SPEC-0014-container-craft-capability-inventory-and-absorption-map.md
> - docs/architecture/spec/superseded/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md
> - docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md
>
> Status: Reference-only for superseded sections.

## Historical document contract

- **Active product requirements** live in [`docs/PRD.md`](../../PRD.md). Treat
  this file as a frozen snapshot for the March 2026 hard-cut program, not as
  an execution checklist for current work.
- **Route authority today:** canonical consumer surface is `/v1/*` plus
  `/metrics/summary` (`ADR-0023`, `SPEC-0000`, `SPEC-0016`). Do not implement
  from the obsolete path names in the subsection below unless you are
  deliberately reproducing historical context.

## PRD: Deployable File Transfer API Platform for Nova Clients

**Date:** 2026-02-12
**Last updated:** 2026-03-19 (archive trim)

### Problem

Provide a reusable file-transfer **control-plane** API so browser clients can
upload and download via S3 without streaming large payloads through app
containers. Consumers include Dash, Shiny, and TypeScript frontends.

### Product goals (durable intent)

1. Stable, documented HTTP contract with OpenAPI 3.1 as the source of truth.
2. Multipart and large-object upload flows within S3 constraints; optional
   Transfer Acceleration when infra enables it.
3. Strong auth boundaries (same-origin and JWT modes), scoped ownership, and
   least-privilege IAM.
4. Async jobs with explicit queue-failure semantics (`503` /
   `queue_unavailable`; failed enqueue not idempotency-cached).
5. Observability: structured logs, bounded metric dimensions, worker queue lag
   and throughput signals.
6. CI/CD and release artifacts aligned with `SPEC-0015` workflow names and
   gates.

### Obsolete route namespace (program-era snapshot only)

During the consolidation program, interim docs referred to `/api/transfers/*`,
`/api/jobs/*`, `/healthz`, and `/readyz`. That namespace was **superseded** by
the hard cut to `/v1/*`, `/v1/health/live`, and `/v1/health/ready`. The
archived program plan in `FINAL-PLAN.md` records those paths as historical
evidence.

### Reliability themes (abbreviated)

For the full rule set, use active specs (`SPEC-0000`, `SPEC-0015`, `SPEC-0016`,
`SPEC-0017`–`SPEC-0019`, `SPEC-0028` as applicable). Themes captured in this
archive include: idempotency claim/commit/discard; legal worker transitions and
`409` on illegal transitions; `succeeded` clears `error`; same-origin scope
precedence for body-less job polling; EMF as top-level structured fields;
readiness excludes feature-flag coupling; blank `FILE_TRANSFER_BUCKET` fails
readiness.

### Capability surface (target era)

Platform capability routes implemented under the `/v1/*` program include
jobs, events, capabilities, resources/plan, releases/info, and health
endpoints, as enumerated in `SPEC-0015` / `SPEC-0000`.

### Non-goals (initial release era)

- No byte-streaming data-plane through FastAPI.
- No default Step Functions/Lambda orchestration.
- No broad compatibility shims outside approved bridge scope (`nova_dash_bridge`).

### Primary users

Frontend integrators (Dash/Shiny/Next.js), platform engineers (`infra/**`),
and runtime engineers (queue, cache, metrics).

### Success metrics (high level)

End-to-end control-plane flows, accurate enqueue failure behavior, correct
readiness, accurate rollups, stable OpenAPI and CI conformance, docs aligned
with implementation.

### Release and quality gates (historical shorthand)

Use the current gates in [`AGENTS.md`](../../../AGENTS.md). At archive time,
monorepo checks included `ruff`, `mypy`, and `pytest`; release flow combined
GitHub Actions with AWS CodePipeline/CodeBuild promotion and signed release
commits.
