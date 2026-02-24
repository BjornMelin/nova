# Nova CI/CD Documentation Index

Status: Active
Owner: nova release architecture
Last reviewed: 2026-02-24

## Purpose

This index is the modular entrypoint for AWS provisioning, secrets, GitHub
integration, and production promotion for the Nova release system.

## Audience

- platform operators deploying CI/CD infrastructure
- application engineers maintaining release workflows
- security reviewers auditing OIDC, IAM, and signing controls

## Conventions

- commands use safe placeholders like `${AWS_ACCOUNT_ID}` and `${AWS_REGION}`
- real secrets are never stored in repo docs
- environment scope is only `dev` and `prod`
- runtime topology is ECS/Fargate + SQS (no Lambda orchestration)

## Execution order

1. [aws-oidc-and-iam-role-setup-guide.md](aws-oidc-and-iam-role-setup-guide.md)
2. [aws-secrets-provisioning-guide.md](aws-secrets-provisioning-guide.md)
3. [config-values-reference-guide.md](config-values-reference-guide.md)
4. [day-0-operator-checklist.md](day-0-operator-checklist.md)
5. [github-actions-secrets-and-vars-setup-guide.md](github-actions-secrets-and-vars-setup-guide.md)
6. [codeconnections-activation-and-validation-guide.md](codeconnections-activation-and-validation-guide.md)
7. [deploy-nova-cicd-end-to-end-guide.md](deploy-nova-cicd-end-to-end-guide.md)
8. [release-promotion-dev-to-prod-guide.md](release-promotion-dev-to-prod-guide.md)
9. [troubleshooting-and-break-glass-guide.md](troubleshooting-and-break-glass-guide.md)
10. [documentation-maintenance-guide.md](documentation-maintenance-guide.md)

## Existing release documents

- [release-runbook.md](RELEASE-RUNBOOK.md)
- [release-policy.md](RELEASE-POLICY.md)
- [nonprod-live-validation-runbook.md](NONPROD-LIVE-VALIDATION-RUNBOOK.md)
- [release-version-manifest.md](RELEASE-VERSION-MANIFEST.md)

## Authoritative external references

- GitHub OIDC in AWS:
  <https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws>
- AWS IAM OIDC provider setup:
  <https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html>
- AWS CodeConnections CloudFormation resource:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-codeconnections-connection.html>
- AWS CodePipeline manual approvals:
  <https://docs.aws.amazon.com/codepipeline/latest/userguide/approvals-action-add.html>
- AWS CodeBuild buildspec reference:
  <https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html>
