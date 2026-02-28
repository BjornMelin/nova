---
Spec: 0014
Title: Container-craft capability inventory and Nova absorption target map
Status: Active
Version: 1.0
Date: 2026-02-28
Related:
  - "[ADR-0014: Absorb remaining container-craft Nova capabilities into nova and retire container-craft](../adr/ADR-0014-container-craft-capability-absorption-and-repo-retirement.md)"
  - "[SPEC-0013: Container-craft capability absorption execution spec](./SPEC-0013-container-craft-capability-absorption-execution-spec.md)"
  - "[SPEC-0004: CI/CD and documentation automation](./SPEC-0004-ci-cd-and-docs.md)"
---

## 1. Purpose

Define the full capability inventory and target absorption map required to remove `container-craft` without Nova capability loss.

Scope is **Nova-required capabilities only** (runtime + release + promotion + operations).

## 2. Classification model

- **Already in Nova**: capability fully implemented and authoritative in `nova`.
- **Partially in Nova**: docs/contracts exist in `nova`, but executable authority remains split with `container-craft`.
- **Missing in Nova**: capability required for Nova operation but currently implemented only in `container-craft`.
- **Obsolete/Not needed**: capability present in `container-craft` but intentionally excluded from Nova final state.

## 3. Full capability inventory map

| Capability area | container-craft source(s) | Classification | Nova target authority | Notes |
| --- | --- | --- | --- | --- |
| Release planning/version manifest logic | N/A (historic split ownership) | Already in Nova | `.github/workflows/release-plan.yml`, `scripts/release/*` | Implemented and tested in Nova. |
| Release apply workflow (OIDC + Secrets Manager) | N/A (historic split ownership) | Already in Nova | `.github/workflows/release-apply.yml` | Implemented and documented in release runbooks. |
| Release buildspec contract | `infra/nova/nova-codebuild-release.yml` references | Partially in Nova | `buildspecs/buildspec-release.yml` + absorbed `infra/nova/nova-codebuild-release.yml` | Buildspec exists; stack template ownership still to absorb. |
| Deploy validation buildspec | `infra/nova/nova-codebuild-release.yml` references | Already in Nova | `buildspecs/buildspec-deploy-validate.yml` | Present; wired through CI/CD stack after absorption. |
| Nova CodePipeline stack | `infra/nova/nova-ci-cd.yml` | Missing in Nova | `infra/nova/nova-ci-cd.yml` | Must become single-source `AppSourceOutput`. |
| Nova IAM role stack | `infra/nova/nova-iam-roles.yml` | Missing in Nova | `infra/nova/nova-iam-roles.yml` | Includes pipeline/build/deploy trust and pass-role boundaries. |
| Nova CodeBuild stack | `infra/nova/nova-codebuild-release.yml` | Missing in Nova | `infra/nova/nova-codebuild-release.yml` | Required for release + validate projects. |
| Digest deployment marker stack | `infra/nova/deploy/image-digest-ssm.yml` | Missing in Nova | `infra/nova/deploy/image-digest-ssm.yml` | Required for immutable promotion marker. |
| ECS service deployment stack | `infra/ecs/service.yml` | Missing in Nova | `infra/runtime/ecs/service.yml` | Required for service runtime provisioning. |
| ECS cluster stack | `infra/ecs/cluster.yml` | Missing in Nova | `infra/runtime/ecs/cluster.yml` | Required where cluster ownership is in-repo. |
| ECR repository stack | `infra/ecr.yml` | Missing in Nova | `infra/runtime/ecr.yml` | Required for image publishing and least privilege ARN scoping. |
| KMS stack | `infra/kms.yml` | Missing in Nova | `infra/runtime/kms.yml` | Required for S3/SQS/secrets encryption policy baseline. |
| File-transfer S3 stack | `infra/file_transfer/s3.yml` | Missing in Nova | `infra/runtime/file_transfer/s3.yml` | Required by SPEC-0002 behaviors. |
| File-transfer cache stack | `infra/file_transfer/cache.yml` | Missing in Nova | `infra/runtime/file_transfer/cache.yml` | Required for cache profile operation under ADR-0007. |
| File-transfer async stack (SQS + DynamoDB + alarms) | `infra/file_transfer/async.yml` | Missing in Nova | `infra/runtime/file_transfer/async.yml` | Required by ADR-0006/SPEC-0008. |
| File-transfer worker ECS stack | `infra/file_transfer/worker.yml` | Missing in Nova | `infra/runtime/file_transfer/worker.yml` | Required for async worker execution. |
| Service discovery stack | `infra/networking/service_discovery.yml` | Partially in Nova | `infra/runtime/networking/service_discovery.yml` or explicit non-use decision | Needed only when service discovery mode is enabled. |
| Auth0 API/SPA infra templates | `infra/auth0/auth_api.yml`, `infra/auth0/service_application.yml` | Partially in Nova | `infra/auth0/*` | Nova has tenant config/mappings; stack templates still external. |
| CodeArtifact domain/repo stacks | `infra/code_artifact/*.yml`, `templates/3m.codeartifact.yml` | Partially in Nova | `infra/runtime/codeartifact/*.yml` | Required if Nova remains first-class publisher to internal package index. |
| Renderer engine | `src/container-craft/container_craft/renderer.py` | Missing in Nova (for absorbed template rendering) | `scripts/infra/render.py` or eliminate via non-templated CFN | Prefer deletion by replacing Jinja indirection with explicit CFN params. |
| Contract validation helpers | `src/container-craft/container_craft/contract_validation.py` | Missing in Nova | `scripts/infra/contract_validation.py` + tests | Must enforce schema/range/path constraints for absorbed templates. |
| Run-mode trigger model | `action.yml` + `settings/service.yml` triggers | Obsolete/Not needed | N/A (replaced by explicit Nova workflows) | Replace generic run modes with deterministic Nova workflows. |
| Falcon wrapper/composite action orchestration | `action.yml` | Obsolete/Not needed | N/A | Not required in final-state Nova architecture. |
| Legacy compatibility toggles | `use_legacy_env_dict`, `use_legacy_task_role_policy`, wildcard secret flags | Obsolete/Not needed | N/A | Explicitly excluded by final-state-only policy. |
| Generic non-Nova workflows (`deploy-all`, etc.) | `.github/workflows/*` in container-craft | Obsolete/Not needed | N/A | Out of Nova scope. |

## 4. Gap-to-build matrix with acceptance tests

| Gap ID | Capability | Nova implementation path | Acceptance tests |
| --- | --- | --- | --- |
| GAP-01 | Nova CI/CD stack ownership | `infra/nova/nova-ci-cd.yml` | Stage graph contract test; no `InfraSourceOutput`; `TemplatePath` from `AppSourceOutput`. |
| GAP-02 | Nova IAM stack ownership | `infra/nova/nova-iam-roles.yml` | IAM lint tests: OIDC trust strictness, pass-role scope, no unapproved wildcard expansion. |
| GAP-03 | Nova CodeBuild stack ownership | `infra/nova/nova-codebuild-release.yml` | Build project contract tests for required env vars and buildspec path correctness. |
| GAP-04 | Digest SSM template ownership | `infra/nova/deploy/image-digest-ssm.yml` | Parameter and path contract test (`/nova/{env}/{service}/image-digest`). |
| GAP-05 | Runtime ECS service stack ownership | `infra/runtime/ecs/service.yml` | CFN lint + policy checks + parameter schema tests for service routing and task sizing. |
| GAP-06 | Runtime ECS cluster stack ownership | `infra/runtime/ecs/cluster.yml` | CFN lint + ALB/listener wiring tests + subnet/vpc validation. |
| GAP-07 | Runtime ECR + KMS ownership | `infra/runtime/ecr.yml`, `infra/runtime/kms.yml` | IAM/KMS least-privilege assertions; encryption at rest controls. |
| GAP-08 | File-transfer S3 ownership | `infra/runtime/file_transfer/s3.yml` | CORS/lifecycle/acceleration contract tests aligned with SPEC-0002. |
| GAP-09 | Async orchestration infra ownership | `infra/runtime/file_transfer/async.yml` | Queue visibility/retry/retention assertions + DynamoDB key schema tests. |
| GAP-10 | Worker stack ownership | `infra/runtime/file_transfer/worker.yml` | Task role permissions + queue/table/bucket env contract tests. |
| GAP-11 | Auth0 stack ownership completion | `infra/auth0/auth_api.yml`, `infra/auth0/service_application.yml` | Template lint and variable contract tests against `infra/auth0/env/*.env.example`. |
| GAP-12 | CodeArtifact stack ownership completion | `infra/runtime/codeartifact/*.yml` | Domain/repo policy and naming contract tests. |
| GAP-13 | Renderer/contract validation replacement | `scripts/infra/*`, `tests/infra/*` | Deterministic render tests; reject legacy toggles and unsafe defaults. |
| GAP-14 | Archive readiness governance | `docs/architecture/spec/SPEC-0013.md` + release runbooks | Gate checklist validation in docs CI. |

## 5. PR expansion plan (full migration coverage)

1. **PR-01: Absorb Nova promotion IaC core** (`infra/nova/**`).
2. **PR-02: Refactor pipeline to single-source artifact model** (remove infra source action).
3. **PR-03: Absorb runtime base templates** (`infra/runtime/{ecs,ecr,kms,networking}/**`).
4. **PR-04: Absorb file-transfer stacks** (`infra/runtime/file_transfer/{s3,cache,async,worker}.yml`).
5. **PR-05: Absorb auth0 and codeartifact stack templates** (if retained in final Nova operating model).
6. **PR-06: Introduce infra contract test suite** (`tests/infra/test_templates_contract.py`, IAM checks).
7. **PR-07: Remove renderer legacy coupling** (explicit parameters, deterministic contracts, no compatibility toggles).
8. **PR-08: Update release/runtime docs and runbooks to Nova-only ownership references.**
9. **PR-09: Nonprod and prod evidence capture** (pipeline runs, digest parity, post-deploy validation).
10. **PR-10: Archive/delete execution for container-craft** once all gates pass.

## 6. Archive/delete hard gates (must all pass)

1. `nova` contains all Nova-required IaC templates with no runtime dependency on `container-craft`.
2. `rg -n "container-craft"` across active Nova release/runtime docs and workflows returns no active-operational references (historical references allowed under `docs/history/`).
3. One successful Dev and one successful Prod promotion using absorbed templates.
4. Immutable digest parity evidence exists for Dev -> Prod promotion.
5. Infra contract test suite passes in CI for absorbed templates.
6. Security checks pass for IAM/KMS/S3/SQS/DynamoDB least privilege and encryption requirements.
7. Release/day-0/troubleshooting runbooks are updated and operator-validated.

## 7. Primary-source evidence notes

- `aws_documentation` MCP server unavailable in this session; replacement evidence sourced from official AWS documentation pages:
  - CodePipeline execution semantics (including multi-source behavior).
  - CodePipeline CloudFormation deploy action reference (`TemplatePath` artifact format and IAM considerations).
  - Source action change detection for CodeConnections.
- Additional tool evidence used from `mcporter`:
  - Exa advanced search (successful).
  - Firecrawl search (successful).
  - Zen analyze/consensus calls attempted; blocked by strict multi-step input requirements/timeouts in this session.
  - Context7 resolved library IDs but did not provide high-fidelity direct AWS CodePipeline user-guide coverage for this question.
