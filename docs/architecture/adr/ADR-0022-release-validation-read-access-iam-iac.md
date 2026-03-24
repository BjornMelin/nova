---
ADR: 0022
Title: Codify release validation read access in Nova IaC
Status: Accepted
Version: 1.0
Date: 2026-03-02
Related:
  - "[ADR-0011: Hybrid CI/CD with GitHub and AWS promotion](./ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](./ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
References:
  - "[AWS IAM policies and permissions boundaries](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html)"
  - "[Amazon ECS infrastructure IAM role for load balancers](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AmazonECSInfrastructureRolePolicyForLoadBalancers.html)"
  - "`infra/nova/nova-iam-roles.yml` (`ReleaseValidationReadManagedPolicy` statements `CodeConnectionsRead`, `ValidationCodeArtifactRead`, `CodePipelineGlobalList`, `CodePipelineScopedRead`, `ValidationRuntime*`)"
---

## Summary

Adopt a dedicated release validation read role in Nova IaC using minimally scoped
read permissions from CodeConnections, CodeArtifact, CodePipeline, CloudFront,
ECS/ELB/WAF, CloudFormation, CloudWatch, and runtime infrastructure IAM surfaces.

## Context

Validation runs were blocked by denied IAM actions from the current operator
context. The target-state read surface now centers on:

- `codeconnections:GetConnection`
- `codepipeline:ListPipelineExecutions`
- `codepipeline:ListPipelines`
- `wafv2:GetWebACLForResource`

Nova required a reproducible, auditable, least-privilege path in-repo
(final-state) instead of ad-hoc/manual grants.

## Decision drivers (weighted)

- Reproducibility (0.40)
- Least privilege + explicit scope (0.30)
- Operational simplicity / low entropy (0.20)
- Auditability (0.10)

## Options considered

1. **Dedicated release validation read role in `infra/nova/nova-iam-roles.yml` with attached managed policy (conditional creation by trusted principal ARN parameter)**
1. Inline role policy instead of a separately managed policy resource
1. Continue manual/operator-side IAM updates out-of-band

## Scoring

| Option | Repro (0.40) | Least Priv (0.30) | Simplicity (0.20) | Audit (0.10) | Weighted score |
| --- | --- | --- | --- | --- | --- |
| 1 | 9.7 | 9.2 | 9.3 | 9.6 | **9.44** |
| 2 | 9.0 | 9.0 | 8.4 | 9.4 | 8.92 |
| 3 | 3.0 | 4.0 | 6.0 | 2.0 | 3.90 |

Only Option 1 reaches the required >=9.0 threshold.

## Consensus pass

A `zen.consensus` pass was executed with multi-model roster (`openai/gpt-5.2`, `google/gemini-3.1-pro-preview`, `x-ai/grok-4.1-fast`).
The first returned perspective aligned with codifying the access in IaC and reinforced boundary/least-privilege posture. Due MCP server thread persistence limitations in this environment, the continuation thread could not be resumed for subsequent model turns. Final decision remains anchored to weighted scoring and primary AWS authorization docs below.

## AWS authorization references used

- AWS Service Authorization Reference -- CodeConnections
- AWS Service Authorization Reference -- CodePipeline
- AWS Service Authorization Reference -- AWS WAFV2
- AWS Service Authorization Reference -- IAM

Key implications used in policy design:

- `codeconnections:GetConnection` supports connection ARN scoping.
- `codeartifact:GetRepositoryEndpoint` and `codeartifact:ReadFromRepository` are
  required for package fetch/read checks during release validation.
- `codeartifact:Describe*` and `codeartifact:List*` read actions are required
  for package/repository/domain metadata validation.
- `codepipeline:ListPipelineExecutions` and other pipeline read APIs support
  pipeline ARN scoping.
- `codepipeline:ListPipelines` is list-level and requires `Resource: "*"`.
- `wafv2:ListWebACLs` is list-level and requires `Resource: "*"`.
- `iam:GetRole` scopes to the explicit ECS infrastructure role ARN.

## Decision

Adopt **Option 1**: codify a dedicated release validation read role in `infra/nova/nova-iam-roles.yml`, created when `ReleaseValidationTrustedPrincipalArn` is provided.

Policy stance:

- Scope to explicit ARNs where service supports it (`codeconnections:GetConnection`,
  pipeline-scoped reads, infrastructure role read).
- Use `Resource: "*"` only where service authorization model requires it
  (`codeartifact:Describe*`/`List*` read APIs and selected runtime list/read APIs).
- Keep conceptual/config surface minimal: single role + single managed policy
  attachment + one principal parameter.

Actions codified in `ReleaseValidationReadManagedPolicy`:

- CodeConnections read: `codestar-connections:GetConnection`,
  `codeconnections:GetConnection`.
- CodeArtifact read: `codeartifact:GetRepositoryEndpoint`,
  `codeartifact:ReadFromRepository`, `codeartifact:GetPackageVersionReadme`,
  `codeartifact:DescribeDomain`, `codeartifact:DescribePackage`,
  `codeartifact:DescribePackageVersion`, `codeartifact:DescribeRepository`,
  `codeartifact:ListPackageVersions`, `codeartifact:ListPackages`,
  `codeartifact:ListRepositoriesInDomain`.
- CodePipeline list/read: `codepipeline:ListPipelines`,
  `codepipeline:ListPipelineExecutions`, `codepipeline:ListActionExecutions`,
  `codepipeline:GetPipeline`, `codepipeline:GetPipelineState`,
  `codepipeline:GetPipelineExecution`.
- Runtime/infrastructure read: `cloudformation:DescribeStacks`,
  `cloudfront:GetDistribution`, `cloudfront:GetDistributionConfig`,
  `cloudfront:GetVpcOrigin`, `cloudfront:ListDistributions`,
  `cloudfront:ListVpcOrigins`, `cloudfront:ListTagsForResource`,
  `ecs:DescribeClusters`, `ecs:ListClusters`, `ecs:ListServices`,
  `ecs:DescribeServices`, `ecs:DescribeTaskDefinition`,
  `elasticloadbalancing:DescribeListeners`,
  `elasticloadbalancing:DescribeRules`,
  `elasticloadbalancing:DescribeTargetHealth`,
  `elasticloadbalancing:DescribeTargetGroups`,
  `elasticloadbalancing:DescribeLoadBalancers`,
  `cloudwatch:GetDashboard`, `cloudwatch:DescribeAlarms`,
  `cloudwatch:GetMetricData`, `cloudwatch:ListDashboards`,
  `wafv2:GetWebACL`, `wafv2:GetWebACLForResource`, `wafv2:ListWebACLs`,
  `iam:GetRole`.

## Consequences

Positive:

- Deterministic and reviewable in PRs.
- Removes manual IAM drift for release gate execution.
- Keeps implementation focused and minimal.

Tradeoffs:

- Requires setting `ReleaseValidationTrustedPrincipalArn` at stack deploy/update time.
- Some actions remain `*` scoped due AWS service authorization constraints.

## Implementation summary

- Added `ReleaseValidationTrustedPrincipalArn` parameter.
- Added `ReleaseValidationReadRole` and attached
  `ReleaseValidationReadManagedPolicy` for read-only release validation access.
- Added conditional output `ReleaseValidationReadRoleArn`.
- Updated runbooks with apply/verify/rollback and evidence expectations.
