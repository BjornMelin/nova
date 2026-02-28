---
Spec: 0013
Title: Container-craft capability absorption execution spec
Status: Active
Version: 1.0
Date: 2026-02-28
Related:
  - "[ADR-0014: Absorb remaining container-craft Nova capabilities into nova and retire container-craft](../adr/ADR-0014-container-craft-capability-absorption-and-repo-retirement.md)"
  - "[ADR-0011: Hybrid CI/CD with GitHub and AWS promotion](../adr/ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[SPEC-0004: CI/CD and documentation automation](./SPEC-0004-ci-cd-and-docs.md)"
---

## 1. Scope and final-state constraints

This specification defines the concrete absorption plan for Nova-required capabilities still present in `container-craft`.

Mandatory constraints:

1. Final-state only: no shims/back-compat wrappers.
2. No AWS CLI credentialed calls required for spec validation steps.
3. Production release quality docs, tests, and runbooks are required before archive.

## 2. Capability inventory and classification

### 2.1 Already in nova

| Capability | container-craft source | nova target/status |
| --- | --- | --- |
| Selective release planning (`changed-units`, `version-plan`) | Previously split responsibility | Implemented in `.github/workflows/release-plan.yml`, `scripts/release/*` |
| Signed release apply with OIDC + Secrets Manager usage | Historical split | Implemented in `.github/workflows/release-apply.yml` |
| Release CodeBuild contracts (`IMAGE_DIGEST`, `PUBLISHED_PACKAGES`, `CHANGED_UNITS`) | `infra/nova/nova-codebuild-release.yml` + buildspec references | Implemented in `buildspecs/buildspec-release.yml` and documented in SPEC-0004 |
| Post-deploy validation endpoints | `buildspecs/buildspec-deploy-validate.yml` reference in template | Implemented in `buildspecs/buildspec-deploy-validate.yml` |
| Operator release runbooks | Historically mixed in infra repos | Implemented in `docs/plan/release/*` |

### 2.2 Partially in nova

| Capability | Gap |
| --- | --- |
| Hybrid CI/CD architecture definition | Architectural docs exist, but execution still references infra from container-craft via dual-source pipeline |
| IAM + promotion stack ownership model | Contract documented, but IaC templates still externalized in container-craft |
| Archive/retirement gate policy | Legacy archive docs exist for prior cutover but no hard kill-gate matrix for container-craft deletion |

### 2.3 Missing in nova (must absorb)

| Capability | Current location | Required nova location |
| --- | --- | --- |
| Nova CodePipeline template (`nova-ci-cd.yml`) | `container-craft/infra/nova/nova-ci-cd.yml` | `nova/infra/nova/nova-ci-cd.yml` |
| Nova CodeBuild project template (`nova-codebuild-release.yml`) | `container-craft/infra/nova/nova-codebuild-release.yml` | `nova/infra/nova/nova-codebuild-release.yml` |
| Nova IAM roles template (`nova-iam-roles.yml`) | `container-craft/infra/nova/nova-iam-roles.yml` | `nova/infra/nova/nova-iam-roles.yml` |
| Digest deployment marker template (`image-digest-ssm.yml`) | `container-craft/infra/nova/deploy/image-digest-ssm.yml` | `nova/infra/nova/deploy/image-digest-ssm.yml` |
| Single-source CodePipeline template wiring | dual-source (`AppSourceOutput` + `InfraSourceOutput`) | single-source (`AppSourceOutput` only; template path from same repo artifact) |

### 2.4 Obsolete / not needed for Nova final state

| Capability class | Rationale |
| --- | --- |
| Generic action `run` modes in `container-craft/action.yml` (`deploy-ecs`, `deploy-ecr`, `deploy-kms`, etc.) | Nova release architecture is already GitHub CI + AWS promotion templates in-repo; generic orchestrator is unnecessary for Nova final state |
| Renderer compatibility toggles (`use_legacy_env_dict`, `use_legacy_task_role_policy`, wildcard secret fallbacks) | Transitional entropy; not required in final-state Nova-controlled IaC |
| Non-Nova workflows in container-craft (`deploy-all.yml`, `deploy-service.yml`, `data-craft.yml`) | Not required for Nova production release control plane |

## 3. Gap-to-build matrix with acceptance tests

| Gap ID | Missing/partial capability | Target implementation path in nova | Acceptance tests (must pass) |
| --- | --- | --- | --- |
| GAP-01 | Missing Nova CodePipeline template ownership | `infra/nova/nova-ci-cd.yml` | CI lints template syntax; contract test asserts stage order = `Source->Build->DeployDev->ValidateDev->(ManualApproval)->DeployProd->ValidateProd`; no `InfraSourceOutput` token present |
| GAP-02 | Missing Nova IAM role template ownership | `infra/nova/nova-iam-roles.yml` | Static IAM assertions: OIDC trust includes strict `aud/sub`; `iam:PassRole` scoped; no wildcard privilege regressions beyond approved patterns |
| GAP-03 | Missing CodeBuild project template ownership | `infra/nova/nova-codebuild-release.yml` | Contract tests validate required environment variables and buildspec path defaults; verify required output variables from buildspec contract |
| GAP-04 | Missing image digest SSM deploy template ownership | `infra/nova/deploy/image-digest-ssm.yml` | Template unit test validates parameter constraints and deterministic SSM parameter path format `/nova/{env}/{service}/image-digest` |
| GAP-05 | Partial architecture (dual-source pipeline) | `infra/nova/nova-ci-cd.yml` refactor | Regression test validates single-source artifact model and valid `TemplatePath` resolution within `AppSourceOutput` |
| GAP-06 | Partial retirement governance | `docs/architecture/spec/SPEC-0013...` + release runbooks | Checklist test (docs lint) requires all archive gates present and linked from release docs |

## 4. PR-by-PR execution expansion (100% migration coverage)

1. **PR-01 — absorb Nova IaC templates**
   - Copy `container-craft/infra/nova/**` into `nova/infra/nova/**`.
   - Keep semantic parity; no behavior changes in this PR.

2. **PR-02 — single-source pipeline refactor**
   - Update `nova/infra/nova/nova-ci-cd.yml` to remove infra-repo source action.
   - Switch deployment `TemplatePath` to `AppSourceOutput::infra/nova/deploy/image-digest-ssm.yml`.

3. **PR-03 — template contract tests**
   - Add tests (e.g., `tests/infra/test_nova_cicd_templates.py`) for stage order, source artifact invariants, role ARN patterns.

4. **PR-04 — IAM hardening assertions**
   - Add static checks for trust policy constraints and restricted pass-role actions.

5. **PR-05 — docs contract update**
   - Update release runbooks and CI/CD docs to reference in-repo Nova IaC only.
   - Remove container-craft as active prerequisite for Nova release path.

6. **PR-06 — nonprod evidence run**
   - Execute dry-run/validation in dev account with existing operational process.
   - Record artifacts: pipeline execution ID, stage evidence, digest value, endpoint validation.

7. **PR-07 — prod readiness and gate sign-off**
   - Confirm manual approval and immutable artifact promotion semantics unchanged.
   - Capture final sign-off evidence and kill criteria checklist.

8. **PR-08 — archive/delete cutover PR**
   - Archive container-craft or remove Nova-specific active references.
   - Update historical docs with retirement timestamp and evidence links.

## 5. Hard archive/delete readiness gates

All gates must be true:

1. **Ownership gate**: `nova/infra/nova/**` contains all active Nova promotion templates.
2. **Reference gate**: No active Nova docs/workflows/templates reference container-craft for release infra authority.
3. **Execution gate**: At least one successful Dev and one successful Prod promotion using absorbed templates.
4. **Immutability gate**: Same image digest promoted Dev→Prod with evidence captured.
5. **Security gate**: IAM static checks pass with no new wildcard escalation.
6. **Runbook gate**: Day-0 + troubleshooting docs updated and validated.
7. **Rollback gate**: documented rollback/redeploy procedure exists for absorbed templates.

## 6. Evidence requirements

Required archival evidence bundle:

- Git commit SHAs for absorbed template introduction and single-source refactor.
- CI logs proving infra template tests and static policy checks pass.
- CodePipeline execution records for nonprod and prod promotion.
- Deployed digest evidence (`IMAGE_DIGEST` + SSM parameter value path).
- Updated runbook/documentation references.

## 7. Implementation notes on MCP research sources

- `aws_documentation` MCP server was not available in this session.
- Replacement evidence was sourced from official AWS docs URLs (CodePipeline behavior, CloudFormation deploy action, source change detection) via web search/fetch tooling.
- `mcporter` tools used during analysis: Exa advanced search (successful), Firecrawl search (successful), Zen analyze/consensus attempts (tool available but session calls timed out/validation-constrained).
