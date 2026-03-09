---
Spec: 0019
Title: CI/CD IAM least-privilege matrix
Status: Active
Version: 1.1
Date: 2026-03-03
Related:
  - "[ADR-0026: OIDC and IAM role partitioning for deploy automation](../adr/ADR-0026-oidc-iam-role-partitioning-for-deploy-automation.md)"
  - "[SPEC-0017: CloudFormation module contract](./SPEC-0017-runtime-component-topology-and-ownership-contract.md)"
  - "[SPEC-0001: Security model](./SPEC-0001-security-model.md)"
---

## 1. Scope

Defines least-privilege IAM boundaries for GitHub OIDC deploy automation,
CloudFormation execution, and CI/CD service roles.

## 2. Principal partitioning

| Principal | Trust source | Responsibility |
| --- | --- | --- |
| GitHub deploy role | GitHub OIDC | Calls deploy workflows and CloudFormation APIs |
| CloudFormation execution roles (dev/prod) | CloudFormation service | Mutates stack resources for target environment |
| CodePipeline role | CodePipeline service | Executes pipeline stages and invokes build/deploy actions |
| CodeBuild project roles | CodeBuild service | Build, validate, and deployment validation tasks |

## 3. Required policy controls

1. `iam:PassRole` is scope-limited to approved role ARNs.
2. `iam:PassRole` policies include `iam:PassedToService` conditions.
3. No wildcard `*` resource grants for role-passing operations.
4. Workflow callers only receive actions required for stack change-set lifecycle
   and evidence collection.

## 4. CI/CD least-privilege matrix

| Operation family | Allowed principal(s) | Required constraints |
| --- | --- | --- |
| `cloudformation:CreateChangeSet`, `ExecuteChangeSet`, `Describe*` | GitHub deploy role | Stack-name scope, region scope |
| `iam:PassRole` for CFN/pipeline roles | GitHub deploy role | ARN allowlist + `iam:PassedToService` |
| `codepipeline:StartPipelineExecution`, `GetPipelineState` | GitHub deploy role / pipeline operators | Named pipeline scope |
| `codepipeline:PutApprovalResult` | Approved promotion actor | Manual approval stage/action scope |
| Resource mutation during deploy | CFN execution roles | Environment stack scope only |

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
