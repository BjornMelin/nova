# Nova documentation router

Status: Active
Current repository state: **canonical wave-2 serverless baseline**
Last reviewed: 2026-03-28

## Purpose

This file routes readers to the active canonical docs set and keeps historical
material out of the default path.

## Read in order

1. `../AGENTS.md`
2. `./architecture/README.md`
3. `./overview/IMPLEMENTATION-STATUS-MATRIX.md`
4. `../README.md`
5. `./standards/README.md`
6. `./runbooks/README.md`

## Active canonical docs

- `./architecture/README.md`
- `./overview/IMPLEMENTATION-STATUS-MATRIX.md`
- `./overview/ACTIVE-DOCS-INDEX.md`
- `./contracts/README.md`
- `./runbooks/README.md`
- `./clients/README.md`
- `./release/README.md`

## Active architecture/program authority

- `./architecture/requirements-wave-2.md`
- `./architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `./architecture/adr/ADR-0034-eliminate-auth-service-and-session-auth.md`
- `./architecture/adr/ADR-0035-replace-generic-jobs-with-export-workflows.md`
- `./architecture/adr/ADR-0036-dynamodb-idempotency-no-redis.md`
- `./architecture/adr/ADR-0037-sdk-generation-consolidation.md`
- `./architecture/adr/ADR-0038-docs-authority-reset.md`
- `./architecture/spec/SPEC-0027-public-api-v2.md`
- `./architecture/spec/SPEC-0028-export-workflow-state-machine.md`
- `./architecture/spec/SPEC-0029-platform-serverless.md`
- `./architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `./architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`

## Historical / superseded

- `./history/README.md`
- `./architecture/adr/superseded/`
- `./architecture/spec/superseded/`
- `./plan/PLAN.md`

## Rules

- Do not treat archived history or superseded ADR/SPEC material as current authority.
- Do not describe ECS/Fargate, runtime worker stacks, or split SDK packages as live repo surfaces.
- Keep docs aligned to the active package graph, GitHub workflows, and `infra/nova_cdk`.
