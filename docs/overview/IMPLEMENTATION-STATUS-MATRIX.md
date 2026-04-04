# Implementation status matrix

Status: Active
Last reviewed: 2026-04-03

Use this file as the active truth model for the canonical Nova baseline.

| Area | Active canonical baseline | Retired / no longer active | Primary docs |
| --- | --- | --- | --- |
| Public auth | bearer JWT only, verified in-process | auth service, session/same-origin auth, split auth SDKs | `ADR-0034`, `SPEC-0027` |
| Async contract | explicit export workflows under `/v1/exports` | generic jobs, internal callback route | `ADR-0035`, `SPEC-0028` |
| Idempotency/state | DynamoDB-backed idempotency with explicit expiration filtering | Redis-backed correctness paths | `ADR-0036`, `SPEC-0029` |
| Transfer control plane | direct-to-S3 uploads with additive initiate hints, DynamoDB-backed upload sessions, AppConfig-backed effective transfer policy resolution with environment fallback, deterministic quota enforcement, policy-scoped transfer acceleration, policy-scoped checksum modes, and dedicated export-copy tuning controls | opaque browser defaults with no durable upload-session state or scoped quota enforcement | `SPEC-0002`, `SPEC-0005`, `SPEC-0027`, `README.md` |
| AWS runtime | Regional REST API + one canonical custom domain via `infra/nova_cdk`, with FastAPI served through the repo-owned Lambda entrypoint (Mangum-backed, zip-packaged, Python 3.13, arm64); WAF is enabled by default in prod and disabled by default in non-prod unless explicitly enabled; Storage Lens, transfer budget notifications, scheduled multipart reconciliation, and the internal SQS-backed export copy worker lane are part of the active operational surface | ECS/Fargate runtime stacks, CloudFront API ingress, Lambda Web Adapter, uvicorn-in-Lambda, and external worker deploy control plane | `ADR-0033`, `SPEC-0028`, `SPEC-0029`, `infra/nova_cdk/README.md` |
| SDK layout | one package per language: `@nova/sdk`, `nova-sdk-py`, R package `nova` | file/auth split packages and `packages/nova_sdk_fetch` | `ADR-0037`, `SPEC-0030`, `docs/clients/CLIENT-SDK-CANONICAL-PACKAGES.md` |
| Release workflows | human-authored release PRs on GitHub `main`, committed `release/RELEASE-PREP.json` plus `release/RELEASE-VERSION-MANIFEST.md`, AWS-native post-merge publish/promote/deploy via CodeConnections + CodePipeline + CodeBuild, `NovaReleaseSupportStack` CloudFormation execution roles, S3-backed release execution manifests, and deploy-output-driven validation | GitHub workflows that publish packages, deploy runtime, promote prod, push release commits to `main`, bot-authored release PRs, free-text URL validation authority, and mixed human/machine release docs | `docs/runbooks/release/README.md`, `docs/runbooks/release/release-runbook.md`, `docs/contracts/release-prep-v1.schema.json`, `docs/contracts/deploy-output-authority-v2.schema.json`, `infra/nova_cdk/README.md` |
| Docs authority | reduced active authority set centered on canonical routers, ADRs, specs, contracts, and runbooks | mixed-wave status language and deleted runtime/deploy docs in active use | `ADR-0038`, `SPEC-0031`, `docs/overview/ACTIVE-DOCS-INDEX.md` |

## Rule

If a branch changes the active package graph, workflows, infrastructure, or
runbook surface, update this matrix in the same change set.
