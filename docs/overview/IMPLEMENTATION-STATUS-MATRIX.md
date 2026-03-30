# Implementation status matrix

Status: Active
Last reviewed: 2026-03-28

Use this file as the active truth model for the canonical Nova baseline.

| Area | Active canonical baseline | Retired / no longer active | Primary docs |
| --- | --- | --- | --- |
| Public auth | bearer JWT only, verified in-process | auth service, session/same-origin auth, split auth SDKs | `ADR-0034`, `SPEC-0027` |
| Async contract | explicit export workflows under `/v1/exports` | generic jobs, internal callback route | `ADR-0035`, `SPEC-0028` |
| Idempotency/state | DynamoDB-backed idempotency with explicit expiration filtering | Redis-backed correctness paths | `ADR-0036`, `SPEC-0029` |
| AWS runtime | Regional REST API + direct Regional WAF + one canonical custom domain via `infra/nova_cdk`, with FastAPI served through a native Lambda handler (zip-packaged, Python 3.13, arm64) | ECS/Fargate runtime stacks, CloudFront API ingress, Lambda Web Adapter, uvicorn-in-Lambda, and worker deploy control plane | `ADR-0033`, `SPEC-0029`, `infra/nova_cdk/README.md` |
| SDK layout | one package per language: `@nova/sdk`, `nova-sdk-py`, R package `nova` | file/auth split packages and `packages/nova_sdk_fetch` | `ADR-0037`, `SPEC-0030`, `docs/clients/CLIENT-SDK-CANONICAL-PACKAGES.md` |
| Release workflows | GitHub workflow-driven selective versioning, immutable API Lambda zip publication in `release-apply`, staged package publish, prod promotion, and route validation | repo-owned CodePipeline/CodeBuild runtime promotion control plane and CDK-local API packaging | `docs/runbooks/release/README.md`, `docs/runbooks/release/release-runbook.md`, `infra/nova_cdk/README.md` |
| Docs authority | reduced active authority set centered on canonical routers, ADRs, specs, contracts, and runbooks | mixed-wave status language and deleted runtime/deploy docs in active use | `ADR-0038`, `SPEC-0031`, `docs/overview/ACTIVE-DOCS-INDEX.md` |

## Rule

If a branch changes the active package graph, workflows, infrastructure, or
runbook surface, update this matrix in the same change set.
