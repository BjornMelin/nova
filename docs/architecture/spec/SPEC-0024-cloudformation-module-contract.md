---
Spec: 0024
Title: CloudFormation module contract
Status: Active
Version: 1.4
Date: 2026-03-20
Supersedes: "[SPEC-0017 (superseded): CloudFormation module contract](./superseded/SPEC-0017-cloudformation-module-contract.md)"
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[ADR-0030: Native-CFN modular stack architecture for Nova infrastructure productization](../adr/ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md)"
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
| `nova-foundation.yml` | Artifact bucket baseline, including lifecycle rules for stack-created buckets, optional CodeConnection resource, manual approval SNS topic, exported shared values |
| `nova-iam-roles.yml` | CI/CD roles, pass-role scopes, service role partitioning, ECS infrastructure role bindings |
| `nova-codebuild-release.yml` | Build/validation CodeBuild projects, retained CloudWatch log groups, and related role bindings |
| `nova-ci-cd.yml` | CodePipeline stages, artifact wiring, promotion controls, manual approval stage, and an intentionally recreatable idle-state control plane |
| `infra/nova/deploy/service-base-url-ssm.yml` | Environment-scoped SSM authority values for deploy validation base URLs (`/nova/{env}/{service}/base-url`) |
| `infra/runtime/**` | Runtime infrastructure (ECS, ALB, WAF, queues, cache, secrets wiring, app parameters, observability) |

Additional runtime ECS service contract:

1. `infra/runtime/ecs/service.yml` owns the ECS service task role and must wire
   `TaskDefinition.TaskRoleArn` to the stack-managed `ECSTaskRole`.
2. Generic operator-provided `TaskRole`, `TaskExecutionSecretArns`, and
   `TaskExecutionSsmParameterArns` parameters are not part of the active module
   contract.
3. Cache-backed runtime secret injection remains an ECS `Secrets` +
   execution-role concern, not a plaintext environment-variable shim.
4. When a runtime ECS service keeps `EnableExecuteCommand: true`, the
   stack-managed task role must include the AWS-required `ssmmessages`
   session-channel permissions needed by ECS Exec. Operators do not restore
   this behavior through external task-role overrides.
5. `AuthMode=jwt_local` may remain the template default while `OidcIssuer`,
   `OidcAudience`, and `OidcJwksUrl` stay blank at template-validation time;
   incomplete local verifier inputs are enforced by Nova readiness/startup
   behavior instead of a self-invalidating CloudFormation rule.

## 4. Inter-stack import/export contract

1. Foundation outputs are imported by IAM, CodeBuild, and CI/CD stacks.
2. Cross-stack values must be explicit via CloudFormation exports/imports.
3. No module may depend on implicit values from undeclared stacks.
4. Deploy validation base URLs are sourced from SSM authority paths managed by
   `infra/nova/deploy/service-base-url-ssm.yml`.

## 5. Template syntax and runtime language contract

1. Deployable templates must be native CloudFormation YAML/JSON.
2. Jinja control syntax is prohibited in deployable templates.
3. Secrets and parameter-store references use native dynamic-reference syntax.

## 6. Deployment semantics

1. Change-set-first execution is required for stack updates.
2. Empty change-sets may be tolerated without failing the workflow.
3. Stack names, capabilities, and parameter payloads are explicit workflow
   inputs.
4. The release control plane (`nova-codebuild-release.yml` and
   `nova-ci-cd.yml`) may be deleted while idle and recreated from repo-owned
   templates when release work resumes.
5. When `nova-foundation.yml` imports an existing artifact bucket through
   `ExistingArtifactBucketName`, equivalent lifecycle controls must be applied
   directly to that bucket because the stack does not own the bucket resource.

## 7. Acceptance criteria

1. Templates pass CFN lint/schema checks.
2. No-Jinja and wiring contract tests pass in `tests/infra`.
3. Foundation-to-control-plane imports are validated by tests.
4. SSM base-url path and HTTPS constraints are validated by tests/docs
   contracts.
5. ECS service task-role ownership, ECS Exec permissions, and secret wiring are
   validated by tests and operator docs.
6. Artifact storage pruning and CodeBuild log retention are documented in the
   release operator guides.

## 8. Traceability

- [NFR-0105](../requirements.md#nfr-0105-contract-traceability)
- [NFR-0106](../requirements.md#nfr-0106-no-shim-posture)
- [IR-0000](../requirements.md#ir-0000-nova-local-runtime-and-release-authority)
- [FR-0013](../requirements.md#fr-0013-ssm-runtime-base-url-authority-for-deploy-validation)
