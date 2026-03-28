# Nova architecture authority map

Status: Active
Current repository state: **canonical wave-2 serverless baseline**
Last reviewed: 2026-03-28

## Purpose

This router defines the active architecture authority for the canonical Nova
system and separates it from historical traceability material.

## Active canonical authority

The active architecture baseline is:

- bearer JWT only
- explicit export workflow resources
- DynamoDB-backed idempotency/state
- HTTP API + Lambda Web Adapter + Step Functions Standard
- unified SDK package layout
- `infra/nova_cdk` as the only active infrastructure implementation path

Use these documents for active architecture decisions and implementation:

- `requirements-wave-2.md`
- `adr/ADR-0033-canonical-serverless-platform.md`
- `adr/ADR-0034-eliminate-auth-service-and-session-auth.md`
- `adr/ADR-0035-replace-generic-jobs-with-export-workflows.md`
- `adr/ADR-0036-dynamodb-idempotency-no-redis.md`
- `adr/ADR-0037-sdk-generation-consolidation.md`
- `adr/ADR-0038-docs-authority-reset.md`
- `spec/SPEC-0027-public-api-v2.md`
- `spec/SPEC-0028-export-workflow-state-machine.md`
- `spec/SPEC-0029-platform-serverless.md`
- `spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `spec/SPEC-0031-docs-and-tests-authority-reset.md`

## Supporting indexes

- `adr/index.md`
- `spec/index.md`
- `../overview/IMPLEMENTATION-STATUS-MATRIX.md`
- `../overview/ACTIVE-DOCS-INDEX.md`

## Historical / superseded

Use only for traceability:

- `adr/superseded/`
- `spec/superseded/`
- `../history/`

## Important rule

Older deploy-governance and ECS-era material may remain in history for audit
purposes, but it is not part of the active architecture surface.
