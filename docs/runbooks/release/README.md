# Release runbooks (index)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-19

## Purpose

Canonical operator docs for **release execution, validation, governance, and
auditability** (where to record outcomes: see `release-policy.md` §6). Provisioning
and first-time setup live under
[`../provisioning/README.md`](../provisioning/README.md).

Committed release artifacts (manifest, generated runtime contract):

- [`../../release/README.md`](../../release/README.md)
- [`../../release/RELEASE-VERSION-MANIFEST.md`](../../release/RELEASE-VERSION-MANIFEST.md)
- [`../../release/runtime-config-contract.generated.md`](../../release/runtime-config-contract.generated.md)

Historical hard-cut checklist:
[`../../history/2026-03-v1-hard-cut/release/HARD-CUTOVER-CHECKLIST.md`](../../history/2026-03-v1-hard-cut/release/HARD-CUTOVER-CHECKLIST.md).

Parent routers: [`../README.md`](../README.md), [`../../plan/PLAN.md`](../../plan/PLAN.md),
[`../../architecture/README.md`](../../architecture/README.md).

## Canonical documentation authority chain

Use this chain for route and HTTP contract authority (link targets instead of
repeating in every guide):

1. [ADR-0023: Hard cut to canonical /v1 surface](../../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)
2. [SPEC-0000: HTTP API contract](../../architecture/spec/SPEC-0000-http-api-contract.md)
3. [SPEC-0016: v1 route namespace and literal guardrails](../../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)
4. [requirements.md](../../architecture/requirements.md)

Full architecture map: [`../../architecture/README.md`](../../architecture/README.md).

## Core policy and execution

| Doc | Role |
| --- | --- |
| [release-policy.md](release-policy.md) | Branching, promotion, security, package rules |
| [release-runbook.md](release-runbook.md) | Plan/apply workflows, preconditions, execution |
| [release-promotion-dev-to-prod.md](release-promotion-dev-to-prod.md) | Immutable dev→prod promotion |

## Live validation

| Doc | Role |
| --- | --- |
| [nonprod-live-validation-runbook.md](nonprod-live-validation-runbook.md) | AWS-live gates: CodeConnections, ALB, pipeline, alarms |
| [browser-live-validation-checklist.md](browser-live-validation-checklist.md) | Browser / `agent-browser` checklist for dash + Nova |

Use **nonprod** for infrastructure and pipeline integration; use **browser**
for deterministic UI/route checks.

## Governance and specialized

| Doc | Role |
| --- | --- |
| [governance-lock-and-branch-protection.md](governance-lock-and-branch-protection.md) | Required checks, branch rules, `gh` verification |
| [auth0-a0deploy-runbook.md](auth0-a0deploy-runbook.md) | Auth0 tenant ops + schema |
| [troubleshooting-and-break-glass.md](troubleshooting-and-break-glass.md) | Failures, break-glass, Batch B read-access notes |

## Audit records

Validation and promotion outcomes are **not** maintained as an append-only file
in this repository. Operators capture durable pointers per
[`release-policy.md`](release-policy.md) §6 (workflow runs, manifest hash,
PR/ticket notes, external object storage when used).

Conventions: **Release operator docs profile** in
[`../../standards/repository-engineering-standards.md`](../../standards/repository-engineering-standards.md).
