# Provisioning runbooks (index)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-28

## Purpose

Minimal setup guidance for the surviving GitHub/AWS release automation and the
canonical serverless CDK stack.

## Active provisioning docs

1. [aws-oidc-and-iam-role-setup.md](aws-oidc-and-iam-role-setup.md)
2. [aws-secrets-provisioning.md](aws-secrets-provisioning.md)
3. [github-actions-secrets-and-vars.md](github-actions-secrets-and-vars.md)
4. [`../../../infra/nova_cdk/README.md`](../../../infra/nova_cdk/README.md)

## Rule

Use `infra/nova_cdk` for infrastructure deployment and synth/diff guidance.
Do not look for active operator paths under deleted repo-owned runtime
CloudFormation or CodePipeline/CodeBuild surfaces.
