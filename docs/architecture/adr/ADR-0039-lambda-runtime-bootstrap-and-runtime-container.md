---
ADR: 0039
Title: Explicit Lambda runtime bootstrap and typed runtime container
Status: Implemented
Version: 1.0
Date: 2026-04-06
Related:
  - "[ADR-0033: Canonical serverless platform](./ADR-0033-canonical-serverless-platform.md)"
  - "[ADR-0038: Reset docs authority](./ADR-0038-docs-authority-reset.md)"
  - "[SPEC-0027: Public API v2](../spec/SPEC-0027-public-api-v2.md)"
  - "[SPEC-0029: Canonical serverless platform](../spec/SPEC-0029-platform-serverless.md)"
---

## Decision

Use one typed `ApiRuntime` container as the only runtime object stored on
`app.state.runtime`, and bootstrap that container explicitly for the Lambda
path before handing requests to Mangum.

For the canonical Lambda entrypoint:

- bootstrap one process-reused `ApiRuntime` container outside Mangum lifespan
- keep Mangum in the Lambda path with `lifespan="off"`
- reuse the same runtime container across warm-process invocations

For non-Lambda app assembly:

- `create_app(runtime=...)` is the pure public app builder around a prebuilt
  runtime container
- `create_managed_app()` is the public builder for local development and other
  lifespan-owned contexts
- caller-managed FastAPI apps that need Mangum lifespan must construct Mangum
  directly instead of routing through Nova's canonical Lambda helper

## Context

The previous runtime model treated FastAPI lifespan as the place to assemble the
heavy runtime graph for every deployment shape. That is acceptable for local
lifespan-owned contexts, but it is the wrong ownership boundary for the Lambda
path when the goal is warm-process reuse.

The previous runtime shape also scattered singleton-like services across many
`app.state.*` attributes and relied on private hooks in tests and perf tooling
for selective bootstrap bypass.

## Why this wins

- aligns Lambda runtime reuse with explicit bootstrap ownership instead of
  Mangum-managed lifespan
- keeps one coherent runtime container instead of a service-locator-style
  collection of `app.state.*` attributes
- gives tests and perf tooling a documented public assembly seam instead of
  private bootstrap flags and provider hooks
- keeps local development straightforward with a managed builder that still owns
  startup and shutdown cleanly

## Consequences

- `app.state.runtime` is the only runtime entrypoint for request dependencies
- request dependencies resolve from the typed runtime container, with thin
  accessors kept only for readability and dependency signatures
- route handlers remain boundary-only adapters; request-owned orchestration
  such as idempotency, activity logging, and request metrics lives in
  application-layer services below the FastAPI router layer
- Lambda bootstrap and local lifespan ownership are both public, explicit
  assembly seams with separate responsibilities
- the canonical Lambda helper owns only the cached-runtime Lambda path; it is
  not a wrapper for arbitrary FastAPI apps
- tests and perf harnesses must build apps through the public runtime/app
  builders rather than mutating app state directly
- the OpenAPI override remains supported, but through a dedicated public module
  instead of being coupled to broader app assembly internals
