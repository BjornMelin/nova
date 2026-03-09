---
Spec: 0026
Title: CI/CD IAM least-privilege matrix
Status: Active
Version: 1.0
Date: 2026-03-05
Related:
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](../adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
  - "[SPEC-0001: Security model](./SPEC-0001-security-model.md)"
  - "[SPEC-0024: CloudFormation module contract](./SPEC-0024-cloudformation-module-contract.md)"
References:
  - "[GitHub OIDC in AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)"
  - "[AWS secure OIDC provider controls](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_oidc_secure-by-default.html)"
  - "[Amazon ECS infrastructure IAM role for load balancers](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AmazonECSInfrastructureRolePolicyForLoadBalancers.html)"
---

## 1. Scope

Defines least-privilege IAM boundaries for GitHub OIDC deploy automation,
CloudFormation execution, ECS infrastructure operations, and CI/CD service
roles.

## 2. Principal partitioning

| Principal | Trust source | Responsibility |
| --- | --- | --- |
| GitHub deploy role | GitHub OIDC | Calls deploy workflows and CloudFormation APIs |
| Release-validation read role | Validation-access OIDC/identity used by PR workflows | Read-only access for release validation evidence and status checks |
| CloudFormation execution roles (dev/prod) | CloudFormation service | Mutates stack resources for target environment |
| ECS infrastructure role | ECS service | Performs load-balancer and service-linked blue/green infrastructure operations |
| CodePipeline role | CodePipeline service | Executes pipeline stages and invokes build/deploy actions |
| CodeBuild project roles | CodeBuild service | Build, validate, and deployment validation tasks |

## 3. Required policy controls

1. `iam:PassRole` is scope-limited to approved role ARNs.
2. `iam:PassRole` policies include `iam:PassedToService` conditions.
3. No wildcard `*` resource grants for role-passing operations where the
   service supports resource scoping.
4. Workflow callers only receive actions required for stack change-set
   lifecycle, evidence collection, and controlled promotion.

## 4. CI/CD least-privilege matrix

| Operation family | Allowed principal(s) | Required constraints |
| --- | --- | --- |
| `cloudformation:CreateChangeSet`, `ExecuteChangeSet`, `Describe*` | GitHub deploy role | Stack-name scope, region scope |
| `iam:PassRole` for CFN/pipeline/ECS infrastructure roles | GitHub deploy role | ARN allowlist + `iam:PassedToService` |
| `codepipeline:StartPipelineExecution`, `GetPipelineState` | GitHub deploy role / pipeline operators | Named pipeline scope |
| Read-only release validation (`codepipeline:GetPipelineState`, artifact and release-metadata read APIs, stack/event describe APIs) | Release-validation read role | Read-only actions only; no mutation/approval actions |
| `codepipeline:PutApprovalResult` | Approved promotion actor | Manual approval stage/action scope |
| Resource mutation during deploy | CFN execution roles / ECS infrastructure role | Environment stack scope only |

## 5. Test and enforcement contract

1. IAM invariants are enforced by infra tests.
2. Policy changes that widen pass-role scope require explicit review and tests.
3. Live rollback/recovery playbooks must document required IAM operations.

## 6. Acceptance criteria

1. IAM contract tests detect wildcard escalation and pass-role drift.
2. Deploy workflows can complete with scoped permissions only.
3. Access-denied failures produce actionable role/action/resource evidence.

## 7. Traceability

- [NFR-0000](../requirements.md#nfr-0000-security-baseline)
- [NFR-0105](../requirements.md#nfr-0105-contract-traceability)
- [IR-0000](../requirements.md#ir-0000-nova-local-runtime-and-release-authority)
