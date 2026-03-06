---
ADR: 0011
Title: Hybrid CI/CD with GitHub CI and AWS-native Dev to Prod promotion
Status: Accepted (umbrella decision; detailed authority delegated to ADR-0030 through ADR-0032)
Version: 1.2
Date: 2026-03-05
Related:
  - "[ADR-0001: Deployment on ECS Fargate behind ALB](./ADR-0001-deployment-on-ecs-fargate-behind-alb.md)"
  - "[ADR-0002: OpenAPI as contract and SDK generation](./ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[ADR-0012: No Lambda runtime scope for release orchestration](./ADR-0012-no-lambda-runtime-scope.md)"
  - "[SPEC-0004: CI/CD and documentation automation](../spec/SPEC-0004-ci-cd-and-docs.md)"
  - "[ADR-0030: Native-CFN modular stack architecture for Nova infrastructure productization](./ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md)"
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](./ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](./ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
References:
  - "[GitHub OIDC in AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)"
  - "[AWS shared OIDC provider controls](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_oidc_secure-by-default.html)"
  - "[CodeConnections CloudFormation resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-codeconnections-connection.html)"
  - "[CodePipeline manual approval](https://docs.aws.amazon.com/codepipeline/latest/userguide/approvals-action-add.html)"
  - "[CodePipeline approval IAM scoping](https://docs.aws.amazon.com/codepipeline/latest/userguide/approvals-iam-permissions.html)"
  - "[CodeBuild buildspec exported variables](https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html)"
---

## Summary

Adopt a hybrid CI/CD model where GitHub Actions owns CI and signed release
state, and AWS CodePipeline/CodeBuild/CloudFormation owns Dev to Prod
promotion. This keeps promotion controls AWS-native while preserving low
maintenance and immutable artifact guarantees.

## Context

- Business/product need: deliver production releases with explicit Dev to Prod
  human approval and auditable evidence capture.
- Technical and operational constraints: no long-lived AWS keys in GitHub,
  least-privilege IAM, signed automation commits, and immutable artifact reuse
  across environments.
- Rejected assumptions and risks discovered: GitHub-only deployment centralizes
  too much deployment authority in repo workflows and weakens AWS-native
  promotion control boundaries for operations teams.
- Related docs: [SPEC-0004](../spec/SPEC-0004-ci-cd-and-docs.md),
  [ADR-0012](./ADR-0012-no-lambda-runtime-scope.md), and
  [requirements](../requirements.md).

## Alternatives

- A: Hybrid GitHub CI plus AWS promotion pipeline.
- B: GitHub-only end-to-end deployment orchestration.
- C: AWS-only CI/CD without GitHub release planning/signing workflow.

## Decision Framework

### Option Scoring

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| **A** | **9.4** | **9.4** | **9.2** | **9.4** | **9.35** |
| B | 9.1 | 9.1 | 9.0 | 9.0 | 9.07 |
| C | 8.6 | 8.8 | 8.5 | 8.7 | 8.65 |

`weighted total = (leverage * 0.35) + (value * 0.30) + (maintenance * 0.25) + (adaptability * 0.10)`

## Decision

Choose Option A: hybrid GitHub CI with AWS-native promotion pipeline.

Implementation commitments:

- GitHub workflows must run quality gates, selective version planning, and
  signed release commit application on `main`.
- AWS CodePipeline must promote immutable artifacts through
  `Build -> DeployDev -> ValidateDev -> ManualApproval -> DeployProd -> ValidateProd`.
- OIDC trust policies must constrain `aud` and `sub` claims to exact repo and
  branch patterns.
- Release-signing material must be read at runtime from AWS Secrets Manager.
- Prod promotion must consume the same artifact identifiers validated in Dev.
- CodeArtifact promotion IAM must use explicit source/destination repository
  parameters and must not rely on domain-wide wildcard repository permissions.

Detailed workflow API, CloudFormation module, and IAM partitioning authority is
owned by `ADR-0030`, `ADR-0031`, and `ADR-0032`.

## Related Requirements

- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
- [NFR-0000](../requirements.md#nfr-0000-security-baseline)
- [IR-0002](../requirements.md#ir-0002-aws-service-dependencies)
- [IR-0001](../requirements.md#ir-0001-sidecar-routing-model)

## Consequences

1. Positive outcomes: release governance is auditable and role-separated while
   preserving fast GitHub CI feedback loops.
2. Trade-offs/costs: added operational components (CodeConnections,
   CodePipeline, CodeBuild projects, IAM roles) and one-time activation steps.
3. Ongoing considerations: manual CodeConnections activation, secrets rotation,
   and runbook evidence discipline remain mandatory for each release cycle.

## Changelog

- 2026-03-05: Reclassified as the umbrella hybrid-pipeline decision with
  detailed deploy-governance authority delegated to `ADR-0030` through
  `ADR-0032`.
- 2026-02-24: Initial ADR acceptance and implementation.
- 2026-02-24: Expanded to full template structure with explicit scoring and
  requirements traceability.

---

## ADR Completion Checklist

- [x] All placeholders (`<…>`) and bracketed guidance are removed/replaced.
- [x] All links are markdown-clickable and resolve to valid local docs or
  sources.
- [x] Context includes concrete constraints, not generic boilerplate.
- [x] Alternatives are decision-relevant and scored consistently.
- [x] Winning row is bold and matches the Decision section.
- [x] Accepted/Implemented ADR score is `>= 9.0`.
- [x] Related requirements link to exact requirement anchors.
- [x] Consequences include both benefits and trade-offs.
