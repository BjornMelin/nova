# Nova documentation router

Status: Active
Current repository state: **canonical serverless baseline with AWS-native release control plane**
Last reviewed: 2026-03-29

## Purpose

This file routes readers to the active canonical docs set, keeps active
supporting docs discoverable, and keeps historical material out of the default
path.

## Read in order

1. `../AGENTS.md`
2. `./architecture/README.md`
3. `./overview/IMPLEMENTATION-STATUS-MATRIX.md`
4. `../README.md`
5. `./standards/README.md`
6. `./runbooks/README.md`
7. `./runbooks/release/release-runbook.md` — if the task is release, deploy, or post-deploy validation

## Active canonical docs

- `./architecture/README.md`
- `./overview/IMPLEMENTATION-STATUS-MATRIX.md`
- `./overview/ACTIVE-DOCS-INDEX.md`
- `./contracts/README.md`
- `./runbooks/README.md`
- `./runbooks/release/release-runbook.md`
- `./clients/README.md`
- `../release/README.md`

## Active architecture/program authority

- `./plan/GREENFIELD-WAVE-2-EXECUTION.md`
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
- `./contracts/deploy-output-authority-v2.schema.json`
- `./contracts/workflow-post-deploy-validate.schema.json`
- `./runbooks/release/release-runbook.md`
- `../infra/nova_cdk/README.md`

## Active supporting architecture/program docs

- `./architecture/adr/index.md`
- `./architecture/spec/index.md`
- `./architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `./architecture/adr/ADR-0011-cicd-hybrid-github-aws-promotion.md`
- `./architecture/adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md`
- `./architecture/adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md`
- `./architecture/adr/ADR-0042-large-file-transfer-phase-0-safety-baseline.md`
- `./architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `./architecture/spec/SPEC-0004-ci-cd-and-docs.md`
- `./architecture/spec/SPEC-0025-reusable-workflow-integration-contract.md`
- `./architecture/spec/SPEC-0026-ci-cd-iam-least-privilege-matrix.md`

## Historical / superseded

- `./history/README.md`
- `./architecture/adr/superseded/`
- `./architecture/spec/superseded/`
- `./plan/PLAN.md`

## Rules

- Do not treat archived history or superseded ADR/SPEC material as current authority.
- Do not move active supporting docs into `superseded/` only because they are not part of the small canonical wave-2 authority set.
- Do not describe ECS/Fargate, runtime worker stacks, or split SDK packages as live repo surfaces.
- Do not treat free-text base URL configuration as runtime authority when a deploy-output artifact is available.
- Keep docs aligned to the active package graph, GitHub workflows, and `infra/nova_cdk`.
