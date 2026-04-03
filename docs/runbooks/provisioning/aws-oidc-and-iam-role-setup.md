# AWS Release IAM Role Setup Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-04-02

## Purpose

Document the current AWS-native release IAM posture for Nova.

Current state:

- the surviving Nova GitHub workflows do not assume AWS roles
- release execution, package publication, and runtime deployment happen inside
  AWS CodePipeline / CodeBuild only
- CloudFormation execution roles are consumed by the AWS-native release control
  plane, not by GitHub Actions

## Prerequisites

1. AWS CLI configured for the target account.
2. Permission to inspect IAM roles and deploy the Nova CDK support stack.
3. The runtime account already has the CDK bootstrap resources and the AWS
   release control plane prerequisites required by `NovaReleaseSupportStack`
   and `NovaReleaseControlPlaneStack`.

## Inputs

- `${AWS_REGION}` default `us-east-1`
- `${AWS_ACCOUNT_ID}`
## Required role capabilities

The active release role boundary is:

- CodePipeline service role executes the pipeline
- CodeBuild release role validates prep, publishes packages, writes manifests,
  and drives CloudFormation change sets
- environment-scoped CloudFormation execution roles mutate runtime resources

GitHub OIDC roles are not required for the surviving Nova release-plan or
post-deploy-validation workflows. If legacy OIDC roles still exist, they
should be removed after the AWS-native release path is verified.

## Authority / references

- `docs/architecture/adr/ADR-0011-cicd-hybrid-github-aws-promotion.md`
- `docs/architecture/adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md`
- `docs/architecture/spec/SPEC-0004-ci-cd-and-docs.md`
- `docs/architecture/spec/SPEC-0026-ci-cd-iam-least-privilege-matrix.md`
- `infra/nova_cdk/src/nova_cdk/release_control_stack.py`
- `infra/nova_cdk/src/nova_cdk/release_support_stack.py`
- `infra/nova_cdk/README.md`

## Step-by-step commands

1. Deploy the support stack if you want the canonical CFN execution roles
   provisioned by Nova rather than passed in from out-of-band IAM.

   ```bash
   npx aws-cdk@2.1107.0 deploy NovaReleaseSupportStack \
     --app "uv run --package nova-cdk python infra/nova_cdk/app.py" \
     -c account=${AWS_ACCOUNT_ID} \
     -c region=${AWS_REGION}
   ```

2. Inspect the support-stack role outputs and trust boundary.

   ```bash
   aws cloudformation describe-stacks \
     --region "${AWS_REGION}" \
     --stack-name NovaReleaseSupportStack \
     --query 'Stacks[0].Outputs'
   ```

3. Confirm the synthesized runtime execution roles are trusted only by
   CloudFormation.

   ```bash
   aws iam get-role \
     --role-name nova-release-dev-cfn-execution \
     --query 'Role.AssumeRolePolicyDocument'
   aws iam get-role \
     --role-name nova-release-prod-cfn-execution \
     --query 'Role.AssumeRolePolicyDocument'
   ```

4. If your account previously hosted GitHub OIDC roles for Nova, inspect and
   retire them after the AWS-native release path is green.

   ```bash
   aws iam list-open-id-connect-providers \
     --query 'OpenIDConnectProviderList[].Arn'
   ```

## Acceptance checks

1. No surviving Nova GitHub workflow requires an AWS OIDC role.
2. `NovaReleaseSupportStack` or explicit equivalent IAM now owns the runtime
   CloudFormation execution-role boundary.
3. The CodeBuild release role can deploy the runtime stacks and only pass the
   approved CloudFormation execution roles.
4. The CloudFormation execution roles are trusted only by CloudFormation and
   own the Route 53/API Gateway/WAF/Lambda/Step Functions mutations for the
   runtime stacks.
