# Provisioning runbooks (index)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-04-10

## Purpose

Minimal setup guidance for the surviving GitHub/AWS release automation and the
canonical serverless CDK stack.

## Active provisioning docs

1. [aws-oidc-and-iam-role-setup.md](aws-oidc-and-iam-role-setup.md)
2. [aws-secrets-provisioning.md](aws-secrets-provisioning.md)
3. [github-actions-secrets-and-vars.md](github-actions-secrets-and-vars.md)
4. [`../../../infra/nova_cdk/README.md`](../../../infra/nova_cdk/README.md)

## Authority / references

- `../../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md` (canonical route-surface authority)
- `../../architecture/adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md`
- `../../architecture/adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md`
- `../../architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `../../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md` (active route-surface guardrails)
- `../../architecture/spec/SPEC-0027-public-api-v2.md`
- `../../architecture/spec/SPEC-0029-platform-serverless.md`
- `../../architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`
- `../../architecture/requirements.md`
- `../release/release-runbook.md`
- `../../../infra/nova_cdk/README.md`

## Rule

Use `infra/nova_cdk` for infrastructure deployment and synth/diff guidance.
Do not look for active operator paths under deleted repo-owned runtime
CloudFormation or CodePipeline/CodeBuild surfaces.
