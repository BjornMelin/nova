# Config Values Reference Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-17

## Purpose

Provide one reference for all values needed to provision runtime stacks,
configure CI/CD stacks, and operate Nova release automation.

## Prerequisites

1. Access to `3M-Cloud/nova` repository.
2. Ability to inspect deployed CloudFormation stack outputs.
3. Existing release stack deployment or planned stack parameter set.

## GitHub repository secrets and vars (`3M-Cloud/nova`)

### Required secrets

- `RELEASE_SIGNING_SECRET_ID`
  - value: Secrets Manager secret ID or ARN for release signing JSON
- `RELEASE_AWS_ROLE_ARN`
  - value: IAM role ARN output `GitHubOIDCReleaseRoleArn`

### Required vars

- `AWS_REGION`
  - default: `us-east-1`
- `CODEARTIFACT_STAGING_REPOSITORY`
  - value: staged publish repository used by package build and promotion source
  - required: yes, default: from `CODEARTIFACT_REPOSITORY_NAME` when unset
- `CODEARTIFACT_PROD_REPOSITORY`
  - value: prod promotion destination repository

## Nova operator command-pack environment keys

Required keys:

- `GITHUB_OIDC_PROVIDER_ARN`
- `SECRET_NAME` (or resolved `RELEASE_SIGNING_SECRET_ARN`)
- `NOVA_ARTIFACT_BUCKET_NAME`
- `AWS_ACCOUNT_ID`
- `SIGNER_NAME`
- `SIGNER_EMAIL`
- `CODEARTIFACT_DOMAIN_NAME`
- `CODEARTIFACT_REPOSITORY_NAME` (fallback default source for staging repo)
- `CODEARTIFACT_STAGING_REPOSITORY`
- `CODEARTIFACT_PROD_REPOSITORY`
- `ECR_REPOSITORY_ARN`

Required ECR targeting:

- `ECR_REPOSITORY_URI`
- `ECR_REPOSITORY_NAME`

Optional keys:

- `EXISTING_CONNECTION_ARN`
- `NOVA_MANUAL_APPROVAL_TOPIC_ARN`
- `CONNECTION_NAME`
- `NOVA_RELEASE_BUILD_PROJECT_NAME`
- `NOVA_DEPLOY_VALIDATE_PROJECT_NAME`
- `NOVA_DEPLOY_SERVICE_NAME`
- `NOVA_DEPLOY_DEV_STACK_NAME`
- `NOVA_DEPLOY_PROD_STACK_NAME`

`NOVA_DEPLOY_DEV_STACK_NAME` / `NOVA_DEPLOY_PROD_STACK_NAME` are digest marker
stack names used by pipeline deploy actions (`infra/nova/deploy/image-digest-ssm.yml`),
not the runtime ECS service stack names.

### Operator contract table

| Key | Required | Default | Consumer |
| --- | --- | --- | --- |
| `CODEARTIFACT_REPOSITORY_NAME` | no | `galaxypy` | fallback only (`CODEARTIFACT_STAGING_REPOSITORY`) |
| `CODEARTIFACT_STAGING_REPOSITORY` | yes | from `CODEARTIFACT_REPOSITORY_NAME` when unset | foundation publish repo + promotion source |
| `CODEARTIFACT_PROD_REPOSITORY` | yes | none | promotion destination |
| `EXISTING_CONNECTION_ARN` | no | empty | foundation/codepipeline connection wiring |
| `NOVA_DEPLOY_SERVICE_NAME` | no | `nova-file-api` | SSM base-url lookup path |

Promotion repository contract:

- `CODEARTIFACT_STAGING_REPOSITORY` and `CODEARTIFACT_PROD_REPOSITORY` MUST be
  different values.
- `CodeArtifactPromotionSourceRepositoryName` is sourced from staging.
- `CodeArtifactPromotionDestinationRepositoryName` is sourced from prod.

Service base URLs are resolved by the operator command pack from SSM parameters:

- `/nova/dev/${NOVA_DEPLOY_SERVICE_NAME:-nova-file-api}/base-url`
- `/nova/prod/${NOVA_DEPLOY_SERVICE_NAME:-nova-file-api}/base-url`

Populate these via `infra/nova/deploy/service-base-url-ssm.yml` before running
`scripts/release/day-0-operator-command-pack.sh`.

## Runtime stack parameter contract

Generated runtime config authority:

- `runtime-config-contract.generated.md` is the operator-facing matrix for
  current runtime env vars, `ENV_VARS_JSON` supported overrides, and ECS
  template wiring.
- Regenerate it with
  `source .venv/bin/activate && uv run python scripts/release/generate_runtime_config_contract.py`.
- The underlying source of truth is
  `packages/nova_file_api/src/nova_file_api/config.py` plus
  `scripts/release/runtime_config_contract.py`.

Documentation authority:
[`../release/README.md#canonical-documentation-authority-chain`](../release/README.md#canonical-documentation-authority-chain).

Capture and manage these runtime values per environment before CI/CD deploy:

- `VPC_ID`
- `SUBNET_IDS`
- `ALB_HOSTED_ZONE_NAME`
- `ALB_HOSTED_ZONE_ID` (optional)
- `ALB_DNS_NAME`
- `ALB_NAME`
- `ALB_SCHEME` (`internal` or `internet-facing`)
- `ENABLE_ALB_ACCESS_LOGS` (`true` or `false`)
- `ALB_LOG_BUCKET` (required only when access logs are enabled)
- `ALB_INGRESS_PREFIX_LIST_ID` or `ALB_INGRESS_CIDR` or
  `ALB_INGRESS_SOURCE_SG_ID` (exactly one)
- `ECS_CLUSTER_NAME`
- `SERVICE_NAME`
- `SERVICE_DNS`
- `DOCKER_REPOSITORY_NAME`
- `IMAGE_DIGEST`
- `ENV_VARS_JSON`
  Use this only for supported non-secret API runtime overrides. The runtime
  deploy script validates the JSON keys against the generated runtime config
  contract and maps them to explicit ECS environment entries; it is no longer
  passed through as `ENV_DICT`.
- `ECS_INFRASTRUCTURE_ROLE_ARN` (optional override; otherwise resolved from the
  control-plane IAM stack)
- `OWNER_TAG`
- `ALARM_ACTION_ARN`
- `ASSIGN_PUBLIC_IP` (`ENABLED` or `DISABLED`)

Retired runtime deploy inputs:

- `TASK_ROLE_ARN`
- `TASK_EXECUTION_SECRET_ARNS`
- `TASK_EXECUTION_SSM_PARAMETER_ARNS`

See:
[`deploy-runtime-cloudformation-environments.md`](deploy-runtime-cloudformation-environments.md)
and
`runtime-config-contract.generated.md`

## CloudFormation stack names and outputs

Default stack names:

- `${project}-${application}-nova-foundation`
- `${project}-${application}-nova-iam-roles`
- `${project}-${application}-nova-codebuild-release`
- `${project}-${application}-nova-ci-cd`
- `${project}-ci-dev-service-base-url`
- `${project}-ci-prod-service-base-url`

Placeholder note:
`${project}` is your project identifier (for example, your org or repo slug),
and `${application}` is the application or service name managed by these stacks.

Canonical SSM base-url marker ownership:

- `/nova/dev/{service}/base-url` is managed only by
  `${project}-ci-dev-service-base-url`.
- `/nova/prod/{service}/base-url` is managed only by
  `${project}-ci-prod-service-base-url`.
- Do not provision additional stacks that manage these same parameter paths.

Critical outputs:

- `GitHubOIDCReleaseRoleArn`
- `PipelineName`
- `ConnectionArn`

## CodeBuild environment contract

Release build project requires:

- `CODEARTIFACT_DOMAIN`
- `CODEARTIFACT_REPOSITORY` (release build publish target)
- `ECR_REPOSITORY_URI` or `ECR_REPOSITORY_NAME`
- `DOCKERFILE_PATH`
- `DOCKER_BUILD_CONTEXT`

Publish/promote workflow contracts additionally require:

- `CODEARTIFACT_STAGING_REPOSITORY`
- `CODEARTIFACT_PROD_REPOSITORY`

## Repo-local npm auth helper

For local developer shells, Nova npm auth is repo-scoped rather than global:

```bash
cd <NOVA_REPO_ROOT>
eval "$(npm run -s codeartifact:npm:env)"
npm install --no-package-lock
```

The helper derives the CodeArtifact npm endpoint and auth token from current
AWS credentials, writes repo-local `.npmrc.codeartifact`, and sets
`NPM_CONFIG_USERCONFIG` to that file. It honors these variables when set:

- `AWS_REGION`
- `CODEARTIFACT_DOMAIN`
- `CODEARTIFACT_STAGING_REPOSITORY`

Do not use `aws codeartifact login --tool npm` for local Nova development on a
workstation because it rewrites global `~/.npmrc` and can break unrelated
repositories. CI workflows may still use it because runners are ephemeral. When
the environment uses npm 10.x, AWS CLI v2.9.5 or newer is required for that
command.

Exported variables:

- `FILE_IMAGE_DIGEST`
- `PUBLISHED_PACKAGES`
- `RELEASE_MANIFEST_SHA256`
- `CHANGED_UNITS`

Reference file:
`buildspecs/buildspec-release.yml`

## Promote-prod workflow dispatch inputs

`promote-prod.yml` requires these runtime inputs:

- `pipeline_name`
- `manifest_sha256`
- `changed_units_json`
- `version_plan_json`
- `promotion_candidates_json`

Source all JSON payload inputs from `publish-packages.yml` gate artifacts.
`manifest_sha256` must equal `RELEASE_MANIFEST_SHA256`, the SHA256 of
`docs/release/RELEASE-VERSION-MANIFEST.md`. If the value is read from
`codeartifact-gate-report.json`, treat that report as a carrier of the
canonical manifest digest rather than the authority itself.
`promotion_candidates_json` may include PyPI, npm, and R candidates. PyPI and
npm entries omit tarball/signature evidence, npm entries keep the package scope
in `package` and the bare scope name in `namespace`, and R entries include
`tarball_sha256` plus `signature_sha256`.

## Endpoint and validation contract

Validation URLs:

- `${DEV_BASE_URL}/v1/transfers/uploads/initiate`
- `${DEV_BASE_URL}/metrics/summary`
- `${DEV_BASE_URL}/v1/jobs`
- `${DEV_BASE_URL}/v1/health/live`
- `${DEV_BASE_URL}/v1/health/ready`
- `${DEV_BASE_URL}/v1/capabilities`
- `${PROD_BASE_URL}/v1/transfers/uploads/initiate`
- `${PROD_BASE_URL}/metrics/summary`
- `${PROD_BASE_URL}/v1/jobs`
- `${PROD_BASE_URL}/v1/health/live`
- `${PROD_BASE_URL}/v1/health/ready`
- `${PROD_BASE_URL}/v1/capabilities`

Documentation authority:
[`../release/README.md#canonical-documentation-authority-chain`](../release/README.md#canonical-documentation-authority-chain).

Route namespace policy:

- Canonical consumer capability namespace is `/v1/*`.
- Release validation inputs MUST include canonical `/v1/*` + `/metrics/summary`
  checks and required legacy-route `404` assertions.
- Legacy route literals are allowed only in dedicated validation `404` checks
  (`validation_legacy_404_paths`), not as active runtime routes.

## File-transfer large-upload contract

Operator/runtime values that now define the large-upload posture:

- `FILE_TRANSFER_MAX_UPLOAD_BYTES=536_870_912_000`
- `FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS=1800`
- `FILE_TRANSFER_PART_SIZE_BYTES=134217728`
- `FILE_TRANSFER_USE_ACCELERATE_ENDPOINT=false` by default

Operational notes:

- `FILE_TRANSFER_USE_ACCELERATE_ENDPOINT=true` requires an acceleration-enabled
  bucket whose name is DNS-compliant and contains no periods.
- Worker result persistence uses direct shared runtime services; callback token
  secrets and stale worker env aliases are not valid inputs.

## References

- Publish packages workflow:
  <https://github.com/3M-Cloud/nova/blob/main/.github/workflows/publish-packages.yml>
- Release apply workflow:
  <https://github.com/3M-Cloud/nova/blob/main/.github/workflows/release-apply.yml>
- Promote prod workflow:
  <https://github.com/3M-Cloud/nova/blob/main/.github/workflows/promote-prod.yml>
- CodeBuild environment variable types:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-codebuild-project-environmentvariable.html>
