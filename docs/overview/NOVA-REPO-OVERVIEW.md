# Nova Runtime Repository Overview

Status: Active
Last reviewed: 2026-03-24

## Purpose

Provide a short mental model for new readers before they move into the
canonical authority docs. This file is orientation only; architecture and
operator authority live elsewhere.

## What Nova Is

Nova is the canonical runtime monorepo for file-transfer orchestration and
in-process bearer JWT verification. It provides a control plane for transfer
and async export workflows and does not proxy file bytes through the API layer.

## Monorepo Map

- `packages/nova_file_api`: canonical `/v1/*` transfer and export-workflow runtime
- `packages/nova_dash_bridge`: Dash/Flask/FastAPI adapters over
  `nova_file_api.public`
- `packages/nova_runtime_support`: shared outer-ASGI request context and
  FastAPI exception registration
- `packages/nova_sdk_py`: release-grade public Python SDK
- `packages/nova_sdk_ts`: release-grade TypeScript SDK in the CodeArtifact
  staged/prod flow
- `packages/nova_sdk_r`: first-class internal R SDK package
- `packages/contracts`: OpenAPI artifacts, workflow schemas, and conformance
  helpers
- `infra/nova` and `infra/runtime`: CI/CD, IAM, and runtime CloudFormation

## Runtime Flow at a Glance

- Requests enter `nova_file_api` on the canonical `/v1/*` surface.
- Bearer JWT verification, validation, idempotency, and service orchestration
  happen in-process.
- Async export workflows publish to queue backends and workers write terminal state through
  the direct-persistence path.
- Health and observability surfaces remain:
  - `/v1/health/live`
  - `/v1/health/ready`
  - `/metrics/summary`

## Package Responsibilities

- `nova_file_api` owns runtime endpoints, auth, export workflow lifecycle, and readiness.
- `nova_dash_bridge` owns framework adapters and consumes
  `nova_file_api.public` as the in-process seam. FastAPI integrations await
  that async surface directly, while Flask/Dash keep explicit sync adapters at
  the true sync edge only.
- `nova_runtime_support` owns shared request-id propagation and shared FastAPI
  exception registration.
- `packages/contracts` owns committed OpenAPI and reusable workflow schema
  artifacts.
- The SDK packages own the generated client surfaces and release artifacts for
  their respective languages.

## Read Next

- `AGENTS.md` for the durable operator contract
- `docs/README.md` for task-based documentation routing
- `docs/architecture/README.md` for canonical architecture authority
- `docs/standards/README.md` for engineering workflow and docs-sync policy
- `docs/runbooks/README.md` for deployment, release, and validation runbooks
- `docs/history/README.md` for archived plans and superseded material
