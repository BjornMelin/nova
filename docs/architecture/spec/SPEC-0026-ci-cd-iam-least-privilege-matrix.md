---
Spec: 0026
Title: CI/CD IAM least-privilege matrix
Status: Active
Version: 1.1
Date: 2026-04-02
Supersedes: "[SPEC-0019 (superseded): CI/CD IAM least-privilege and role-boundary contract](./superseded/SPEC-0019-ci-cd-iam-least-privilege-and-role-boundary-contract.md)"
Related:
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](../adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
  - "[SPEC-0001: Security model](./SPEC-0001-security-model.md)"
  - "[SPEC-0004: CI/CD and documentation automation](./SPEC-0004-ci-cd-and-docs.md)"
References:
  - "[CodePipeline service role guidance](https://docs.aws.amazon.com/codepipeline/latest/userguide/how-to-custom-role.html)"
  - "[CodeBuild environment variable guidance](https://docs.aws.amazon.com/codebuild/latest/APIReference/API_EnvironmentVariable.html)"
  - "[IAM pass role conditions](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_passrole.html)"
---

## 1. Scope

Defines least-privilege IAM boundaries for the AWS-native Nova release control
plane, `NovaReleaseSupportStack` environment-scoped CloudFormation execution
roles, and the optional read-only GitHub validation surface.

## 2. Principal partitioning

| Principal | Trust source | Responsibility |
| --- | --- | --- |
| CodePipeline role | CodePipeline service | Executes pipeline stages and invokes build/deploy actions |
| CodeBuild release role | CodeBuild service | Validate prep, publish packages, write manifests, and drive CloudFormation change sets |
| CloudFormation execution role (dev) | CloudFormation service | Mutates dev runtime resources only |
| CloudFormation execution role (prod) | CloudFormation service | Mutates prod runtime resources only |
| Optional read-only validation role | External read-only identity if kept at all | Reads release/runtime evidence only |

## 3. Required policy controls

1. `iam:PassRole` is scope-limited to approved role ARNs.
2. `iam:PassRole` policies include `iam:PassedToService` conditions.
3. No wildcard `*` resource grants for role-passing operations where the
   service supports resource scoping.
4. GitHub-hosted workflows do not receive release, promotion, approval, or
   runtime-deploy permissions.
5. `NovaReleaseSupportStack` is the canonical provider of the default dev/prod
   CloudFormation execution roles unless explicit equivalent ARNs are supplied.

## 4. CI/CD least-privilege matrix

| Operation family | Allowed principal(s) | Required constraints |
| --- | --- | --- |
| `codepipeline:Get*`, `List*`, `PutApprovalResult` | Pipeline operators and manual approvers | Named pipeline scope only |
| `codeartifact:GetRepositoryEndpoint`, `ReadFromRepository`, `PublishPackageVersion`, `CopyPackageVersions` | CodeBuild release role | Domain/repository/package scope only |
| `secretsmanager:GetSecretValue` | CodeBuild release role | Signing secret ARN scope only |
| `ssm:GetParameter` | CodeBuild release role | Runtime-config parameter ARN scope only |
| `cloudformation:CreateChangeSet`, `ExecuteChangeSet`, `Describe*`, `DeleteChangeSet`, `GetTemplate*` | CodeBuild release role | Runtime stack-name scope only |
| `iam:PassRole` for CloudFormation execution roles | CodeBuild release role | Exact ARN allowlist + `iam:PassedToService=cloudformation.amazonaws.com` |
| `codepipeline:PutApprovalResult` | Approved promotion actor | Manual approval stage/action scope |
| `ssm:GetParameters` for `/cdk-bootstrap/<qualifier>/version` | CloudFormation execution roles only | Bootstrap version parameter ARN scope only |
| AppConfig mutation during deploy | CloudFormation execution roles only | Create actions require Nova request tags; non-create actions require Nova resource tags; no unscoped AppConfig admin grant |
| Route53 record changes during deploy | CloudFormation execution roles only | Hosted-zone ARN scope only |
| CloudWatch alarm/dashboard mutation during deploy | CloudFormation execution roles only | Named Nova alarm/dashboard ARN scope only; list/read actions may remain `*` when AWS requires it |
| SNS and SQS mutation during deploy | CloudFormation execution roles only | Named Nova topic/queue ARN scope only |
| Budget mutation during deploy | CloudFormation execution roles only | Named Nova budget ARN scope only |
| Resource mutation during deploy | CloudFormation execution roles only | Environment stack scope only |
| Read-only release/runtime evidence access | Optional read-only validation role | No mutation or approval actions |

## 5. Test and enforcement contract

1. IAM invariants are enforced by infra tests.
2. Policy changes that widen pass-role scope require explicit review and tests.
3. Live rollback/recovery playbooks must document required IAM operations.

## 6. Acceptance criteria

1. IAM contract tests detect wildcard escalation and pass-role drift.
2. Release builds can complete with scoped permissions only.
3. Access-denied failures produce actionable role/action/resource evidence.

## 7. Traceability

- [NFR-0000](../requirements.md#nfr-0000-security-baseline)
- [NFR-0105](../requirements.md#nfr-0105-contract-traceability)
- [IR-0000](../requirements.md#ir-0000-nova-local-runtime-and-release-authority)
