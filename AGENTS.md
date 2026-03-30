# AGENTS.md (nova)

Nova is now in the **canonical wave-2 serverless baseline**.

Use this file to keep active authority small and explicit.

## Read in order

1. `docs/README.md`
2. `docs/architecture/README.md`
3. `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
4. `README.md`
5. `docs/standards/README.md`
6. `docs/runbooks/README.md`
7. `docs/plan/PLAN.md` for program-history context only

## Active canonical authority

The active implementation and operating baseline is the same canonical system:

- bearer JWT only
- explicit export workflow resources under `/v1/exports`
- DynamoDB-backed idempotency/state
- Regional REST API + native Lambda handler + Step Functions Standard
- unified SDK package layout for TypeScript, Python, and R
- `infra/nova_cdk` as the only active infrastructure implementation surface

Primary active authority:

- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `docs/architecture/adr/ADR-0034-eliminate-auth-service-and-session-auth.md`
- `docs/architecture/adr/ADR-0035-replace-generic-jobs-with-export-workflows.md`
- `docs/architecture/adr/ADR-0036-dynamodb-idempotency-no-redis.md`
- `docs/architecture/adr/ADR-0037-sdk-generation-consolidation.md`
- `docs/architecture/adr/ADR-0038-docs-authority-reset.md`
- `docs/architecture/spec/SPEC-0027-public-api-v2.md`
- `docs/architecture/spec/SPEC-0028-export-workflow-state-machine.md`
- `docs/architecture/spec/SPEC-0029-platform-serverless.md`
- `docs/architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `docs/architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`

## Historical / superseded

Treat these as traceability only:

- `docs/history/**`
- `docs/architecture/adr/superseded/**`
- `docs/architecture/spec/superseded/**`

## Core laws

- Do not reintroduce auth-service, session-auth, generic-job, Redis, ECS/Fargate, or split-SDK assumptions into active code, CI, docs, or release workflows.
- Keep `infra/nova_cdk` as the only active infrastructure path.
- Keep package release automation aligned to the unified package graph only.
- If code, contracts, package layout, CI, or runbooks change, update the corresponding active docs in the same branch.
