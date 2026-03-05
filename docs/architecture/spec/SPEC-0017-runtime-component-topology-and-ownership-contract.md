---
Spec: 0017
Title: CloudFormation module contract
Status: Active
Version: 1.2
Date: 2026-03-05
Related:
  - "[ADR-0024: Native-CFN modular stack architecture for Nova infrastructure productization](../adr/ADR-0024-layered-architecture-authority-pack.md)"
  - "[ADR-0029: SSM runtime base URL authority for deploy validation](../adr/ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md)"
  - "[SPEC-0004: CI/CD and documentation automation](./SPEC-0004-ci-cd-and-docs.md)"
  - "[SPEC-0015: Nova API platform final topology and delivery contract](./SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md)"
  - "[SPEC-0023: SSM runtime base-url contract for deploy validation](./SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md)"
---

## 1. Scope

Defines the required module structure and inter-stack contract for Nova native
CloudFormation templates.

## 2. Canonical stack modules

Required stack modules:

1. `infra/nova/nova-foundation.yml`
2. `infra/nova/nova-iam-roles.yml`
3. `infra/nova/nova-codebuild-release.yml`
4. `infra/nova/nova-ci-cd.yml`
5. `infra/nova/deploy/service-base-url-ssm.yml`
6. runtime stacks under `infra/runtime/**`

## 3. Module ownership and responsibilities

| Module | Required responsibilities |
| --- | --- |
| `nova-foundation.yml` | Artifact bucket baseline, optional CodeConnection resource, manual approval SNS topic, exported shared values |
| `nova-iam-roles.yml` | CI/CD roles, pass-role scopes, service role partitioning |
| `nova-codebuild-release.yml` | Build/validation CodeBuild projects and related role bindings |
| `nova-ci-cd.yml` | CodePipeline stages, artifact wiring, promotion controls, manual approval stage |
| `infra/nova/deploy/service-base-url-ssm.yml` | Environment-scoped SSM authority values for deploy validation base URLs (`/nova/{env}/{service}/base-url`) |
| `infra/runtime/**` | Runtime infrastructure (ECS, ALB, cache, secrets wiring, app parameters) |

## 4. Inter-stack import/export contract

1. Foundation outputs are imported by IAM, CodeBuild, and CI/CD stacks.
2. Cross-stack values must be explicit via CloudFormation exports/imports.
3. No module may depend on implicit values from undeclared stacks.
4. Deploy validation base URLs are sourced from SSM authority paths managed by
   `infra/nova/deploy/service-base-url-ssm.yml`.

## 5. Template syntax and runtime language contract

1. Deployable templates MUST be native CloudFormation YAML/JSON.
2. Jinja control syntax (for example `{% if %}`) is prohibited in deployable
   templates.
3. Secrets and parameter-store references use native dynamic-reference syntax.

## 6. Deployment semantics

1. Change-set-first execution is required for stack updates.
2. Empty change-sets may be tolerated without failing the workflow.
3. Stack names, capabilities, and parameter payloads are explicit workflow
   inputs.

## 7. Acceptance criteria

1. Templates pass CFN lint/schema checks.
2. No-Jinja and wiring contract tests pass in `tests/infra`.
3. Foundation-to-control-plane imports are validated by tests.
4. SSM base-url path and HTTPS constraints are validated by tests/docs contracts.

## 8. Traceability

- [NFR-0105](../requirements.md#nfr-0105-contract-traceability)
- [NFR-0106](../requirements.md#nfr-0106-no-shim-posture)
- [IR-0000](../requirements.md#ir-0000-nova-local-runtime-and-release-authority)
- [FR-0013](../requirements.md#fr-0013-ssm-runtime-base-url-authority-for-deploy-validation)
