---
ADR: 0011
Title: Human GitHub release PRs with AWS-native post-merge execution
Status: Accepted
Version: 1.3
Date: 2026-04-02
Related:
  - "[ADR-0002: OpenAPI as contract and SDK generation](./ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[SPEC-0004: CI/CD and documentation automation](../spec/SPEC-0004-ci-cd-and-docs.md)"
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](./ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](./ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
  - "[ADR-0033: Canonical serverless platform](./ADR-0033-canonical-serverless-platform.md)"
  - "[SPEC-0029: Canonical serverless platform](../spec/SPEC-0029-platform-serverless.md)"
References:
  - "[CloudFormation service role](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-iam-servicerole.html)"
  - "[CodeConnections CloudFormation resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-codeconnections-connection.html)"
  - "[CodePipeline manual approval](https://docs.aws.amazon.com/codepipeline/latest/userguide/approvals-action-add.html)"
  - "[CodePipeline approval IAM scoping](https://docs.aws.amazon.com/codepipeline/latest/userguide/approvals-iam-permissions.html)"
  - "[CodeBuild buildspec exported variables](https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html)"
---

## Summary

Adopt a human-reviewed GitHub plus AWS-native post-merge release model where
GitHub owns PR CI and release-prep review, and AWS CodeConnections /
CodePipeline / CodeBuild own publish, promotion, and runtime deployment from
merged `main`.

## Context

- Business/product need: deliver production releases with explicit Dev to Prod
  human approval and auditable evidence capture.
- Technical and operational constraints: no long-lived AWS keys in GitHub,
  least-privilege IAM, protected branches that cannot rely on bot bypass
  actors, and immutable artifact reuse across environments.
- Rejected assumptions and risks discovered: GitHub-only deployment centralizes
  too much deployment authority in repo workflows and weakens AWS-native
  promotion control boundaries for operations teams.
- Related docs: [SPEC-0004](../spec/SPEC-0004-ci-cd-and-docs.md),
  [ADR-0012](./superseded/ADR-0012-no-lambda-runtime-scope.md), and
  [requirements](../requirements.md).

## Alternatives

- A: Human release PRs in GitHub plus AWS-native post-merge execution.
- B: GitHub-only read-only release execution after removing commit pushes.
- C: AWS-only CI/CD without GitHub PR/review as the source gate.

## Decision Framework

### Option Scoring

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| **A** | **9.3** | **9.3** | **9.1** | **9.3** | **9.24** |
| B | 8.8 | 8.9 | 8.8 | 8.7 | 8.82 |
| C | 8.3 | 8.4 | 7.8 | 8.5 | 8.18 |

`weighted total = (leverage * 0.35) + (value * 0.30) + (maintenance * 0.25) + (adaptability * 0.10)`

## Decision

Choose Option A: GitHub human release PRs plus AWS-native post-merge execution.

Implementation commitments:

- GitHub workflows must stay read-only with respect to protected branches.
- Human operators must prepare release PRs locally from repo-native release
  planning output.
- AWS CodePipeline must run
  `ValidateReleasePrep -> PublishAndDeployDev -> ManualApproval -> PromoteAndDeployProd`.
- Runtime CloudFormation execution roles must be trusted only by
  `cloudformation.amazonaws.com` and passed to deploy stages explicitly.
- Release-signing material must be read at runtime from AWS Secrets Manager
  when package signatures are required.
- Prod promotion must consume the same artifact identifiers validated in Dev.
- CodeArtifact promotion IAM must use explicit source/destination repository
  parameters and must not rely on domain-wide wildcard repository permissions.

## Related Requirements

- [ADR-0023: Canonical V1 route surface hard-cut](./ADR-0023-hard-cut-v1-canonical-route-surface.md)
- [SPEC-0016: V1 route namespace and literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)
- [SPEC-0029: Canonical serverless platform](../spec/SPEC-0029-platform-serverless.md)
- [requirements.md](../requirements.md) (requirements baseline)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
- [NFR-0000](../requirements.md#nfr-0000-security-baseline)
- [IR-0002](../requirements.md#ir-0002-aws-service-dependencies)
- [IR-0001](../requirements.md#ir-0001-sidecar-routing-model)

## Consequences

1. Positive outcomes: release governance is auditable and role-separated while
   eliminating the need for GitHub bot push rights on protected branches.
2. Trade-offs/costs: added operational components (CodeConnections,
   CodePipeline, CodeBuild projects, IAM roles) and one-time activation steps.
3. Ongoing considerations: manual CodeConnections activation, secrets rotation,
   and runbook evidence discipline remain mandatory for each release cycle.

## Changelog

- 2026-04-02: Updated the decision to human-authored release PRs plus AWS-native
  post-merge execution after removing protected-branch bot mutation assumptions.
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
