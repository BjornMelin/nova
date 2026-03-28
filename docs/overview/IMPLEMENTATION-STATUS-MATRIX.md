# Implementation status matrix

Status: Active
Last reviewed: 2026-03-25

Use this file to keep current-baseline truth and target-state direction separate.

| Area | Current implemented baseline | Approved target state | Primary docs |
| --- | --- | --- | --- |
| Public auth | bearer JWT only, verified in-process; no public session or same-origin auth path | remove remaining legacy auth assets and docs drift | `docs/architecture/adr/ADR-0034-*`, `docs/architecture/spec/SPEC-0027-*` |
| Async contract | explicit export workflows under `/v1/exports` | retire remaining generic-job references and legacy downstream assumptions | `ADR-0035`, `SPEC-0028` |
| Internal async completion | workflow-native export state, no internal callback route in the active API contract | retire residual legacy worker/callback documentation and assets | `ADR-0035`, `SPEC-0028` |
| Idempotency/state | DynamoDB-backed idempotency with explicit expiration filtering; local cache is optimization only | retire residual Redis-era docs/assets from active surfaces | `ADR-0036`, `SPEC-0029` |
| AWS runtime | HTTP API + Lambda Web Adapter + Step Functions Standard components are landed in-repo; legacy ECS-era assets remain as non-canonical leftovers | complete legacy ECS-era retirement from active runbooks/assets | `ADR-0033`, `SPEC-0029` |
| SDK layout | one package per language: `@nova/sdk`, `nova-sdk-py`, and R package `nova` | remove any remaining stale split-package references from docs/examples/release surfaces | `ADR-0037`, `SPEC-0030`, `docs/clients/CLIENT-SDK-CANONICAL-PACKAGES.md` |
| Docs authority | reduced active authority set with wave-1 archived/superseded and tracked docs as the only active merge surface | finish the remaining router/index truth-model cleanup on this branch | `ADR-0038`, `SPEC-0031`, `docs/overview/ACTIVE-DOCS-INDEX.md` |
| Operations | current provisioning/release runbooks remain authoritative where legacy environments still exist; serverless operational guidance is also active for the landed platform components | remove ECS-centric runbooks from active use once legacy environments are formally retired | `docs/runbooks/README.md`, `docs/runbooks/RUNBOOK-SERVERLESS-OPERATIONS.md` |

## Rule

If a branch merges and changes one of these rows, update this matrix in the same
change set.
