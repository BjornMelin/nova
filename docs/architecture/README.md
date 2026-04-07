# Nova architecture authority map

Status: Active
Current repository state: **canonical wave-2 serverless baseline**
Last reviewed: 2026-04-07

## Purpose

This router defines the active architecture authority for the canonical Nova
system and separates it from historical traceability material.

## Active canonical authority

The active architecture baseline is:

- bearer JWT only
- explicit export workflow resources
- DynamoDB-backed idempotency/state
- Regional REST API + direct Regional WAF + one canonical custom domain
- unified SDK package layout
- `infra/nova_cdk` as the only active infrastructure implementation path

Use these documents for active architecture decisions and implementation:

- `../plan/GREENFIELD-WAVE-2-EXECUTION.md`
- `adr/ADR-0033-canonical-serverless-platform.md`
- `adr/ADR-0034-eliminate-auth-service-and-session-auth.md`
- `adr/ADR-0035-replace-generic-jobs-with-export-workflows.md`
- `adr/ADR-0036-dynamodb-idempotency-no-redis.md`
- `adr/ADR-0037-sdk-generation-consolidation.md`
- `adr/ADR-0038-docs-authority-reset.md`
- `adr/ADR-0039-lambda-runtime-bootstrap-and-runtime-container.md`
- `spec/SPEC-0027-public-api-v2.md`
- `spec/SPEC-0028-export-workflow-state-machine.md`
- `spec/SPEC-0029-platform-serverless.md`
- `spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `spec/SPEC-0031-docs-and-tests-authority-reset.md`
- `../contracts/deploy-output-authority-v2.schema.json`
- `../contracts/workflow-post-deploy-validate.schema.json`
- `../runbooks/release/release-runbook.md`
- `../../infra/nova_cdk/README.md`

## Active supporting current-state docs

These docs remain current and useful even though they are not part of the
small canonical wave-2 authority core:

- `adr/index.md`
- `spec/index.md`
- `adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `adr/ADR-0011-cicd-hybrid-github-aws-promotion.md`
- `adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md`
- `adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md`
- `adr/ADR-0042-large-file-transfer-observability-and-benchmark-baseline.md`
- `spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `spec/SPEC-0004-ci-cd-and-docs.md`
- `spec/SPEC-0025-reusable-workflow-integration-contract.md`
- `spec/SPEC-0026-ci-cd-iam-least-privilege-matrix.md`

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
purposes, but it is not part of the active architecture surface. Current
supporting docs stay at the root `adr/` and `spec/` levels; superseded docs
live under `adr/superseded/` and `spec/superseded/`.
Do not reintroduce CloudFront as a compensating API ingress layer or treat the
default `execute-api` hostname as an active public endpoint.
Treat deploy-output authority as the published runtime source of truth for the
custom-domain base URL and release provenance.
