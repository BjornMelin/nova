# Config Values Reference Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-06

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

Artifact bucket authority:

- `NOVA_ARTIFACT_BUCKET_NAME` is CI/CD storage for signed release artifacts,
  manifests, and pipeline handoff data.
- It is not the runtime upload/download bucket.
- Do not reuse `NOVA_ARTIFACT_BUCKET_NAME` as the file-transfer bucket for
  `infra/runtime/file_transfer/s3.yml`.

Optional keys:

- `EXISTING_CONNECTION_ARN`
- `NOVA_MANUAL_APPROVAL_TOPIC_ARN`
- `CONNECTION_NAME`
- `NOVA_RELEASE_BUILD_PROJECT_NAME`
- `NOVA_DEPLOY_VALIDATE_PROJECT_NAME`
- `NOVA_DEPLOY_SERVICE_NAME`
- `NOVA_DEPLOY_DEV_STACK_NAME`
- `NOVA_DEPLOY_PROD_STACK_NAME`
- `NOVA_AUTH_DEPLOY_SERVICE_NAME`
- `NOVA_AUTH_DEPLOY_DEV_STACK_NAME`
- `NOVA_AUTH_DEPLOY_PROD_STACK_NAME`
- `RELEASE_VALIDATION_TRUSTED_PRINCIPAL_ARN`
- `ECS_INFRASTRUCTURE_ROLE_ARN`
- `DEPLOYMENT_ROLLBACK_ALARM_NAME_PRIMARY`
- `DEPLOYMENT_ROLLBACK_ALARM_NAME_SECONDARY`

`NOVA_DEPLOY_DEV_STACK_NAME` / `NOVA_DEPLOY_PROD_STACK_NAME` are digest marker
stack names used by pipeline deploy actions (`infra/nova/deploy/image-digest-ssm.yml`),
not the runtime ECS service stack names.
`NOVA_AUTH_DEPLOY_DEV_STACK_NAME` / `NOVA_AUTH_DEPLOY_PROD_STACK_NAME` follow
the same contract for the auth API image-digest markers.

### Operator contract table

| Key | Required | Default | Consumer |
| --- | --- | --- | --- |
| `CODEARTIFACT_REPOSITORY_NAME` | no | `galaxypy` | fallback only (`CODEARTIFACT_STAGING_REPOSITORY`) |
| `CODEARTIFACT_STAGING_REPOSITORY` | yes | from `CODEARTIFACT_REPOSITORY_NAME` when unset | foundation publish repo + promotion source |
| `CODEARTIFACT_PROD_REPOSITORY` | yes | none | promotion destination |
| `EXISTING_CONNECTION_ARN` | no | empty | foundation/codepipeline connection wiring |
| `NOVA_DEPLOY_SERVICE_NAME` | no | `nova-file-api` | SSM base-url lookup path |
| `NOVA_AUTH_DEPLOY_SERVICE_NAME` | no | `nova-auth-api` | auth SSM base-url lookup path |
| `RELEASE_VALIDATION_TRUSTED_PRINCIPAL_ARN` | no | empty | `infra/nova/nova-iam-roles.yml` `ReleaseValidationTrustedPrincipalArn` |
| `ECS_INFRASTRUCTURE_ROLE_ARN` | yes for ECS native blue/green | none | `infra/runtime/ecs/service.yml` `EcsInfrastructureRoleArn` |
| `DEPLOYMENT_ROLLBACK_ALARM_NAME_PRIMARY` | yes for ECS native blue/green | none | primary CloudWatch rollback alarm for `AWS::ECS::Service` |
| `DEPLOYMENT_ROLLBACK_ALARM_NAME_SECONDARY` | yes for ECS native blue/green | none | secondary CloudWatch rollback alarm for `AWS::ECS::Service` |

Promotion repository contract:

- `CODEARTIFACT_STAGING_REPOSITORY` and `CODEARTIFACT_PROD_REPOSITORY` MUST be
  different values.
- `CodeArtifactPromotionSourceRepositoryName` is sourced from staging.
- `CodeArtifactPromotionDestinationRepositoryName` is sourced from prod.

Service base URLs are resolved by the operator command pack from SSM parameters:

- `/nova/dev/${NOVA_DEPLOY_SERVICE_NAME:-nova-file-api}/base-url`
- `/nova/prod/${NOVA_DEPLOY_SERVICE_NAME:-nova-file-api}/base-url`
- `/nova/dev/${NOVA_AUTH_DEPLOY_SERVICE_NAME:-nova-auth-api}/base-url`
- `/nova/prod/${NOVA_AUTH_DEPLOY_SERVICE_NAME:-nova-auth-api}/base-url`

Populate these via `infra/nova/deploy/service-base-url-ssm.yml` before running
`scripts/release/day-0-operator-command-pack.sh`.

## Runtime stack parameter contract

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
- `TASK_ROLE_ARN`
- `ECS_INFRASTRUCTURE_ROLE_ARN`
- `DOCKER_REPOSITORY_NAME`
- `DOCKER_IMAGE_TAG`
- `OWNER_TAG`
- `ALARM_ACTION_ARN`
- `DEPLOYMENT_ROLLBACK_ALARM_NAME_PRIMARY`
- `DEPLOYMENT_ROLLBACK_ALARM_NAME_SECONDARY`
- `ASSIGN_PUBLIC_IP` (`DISABLED` only for Nova dev/prod release environments)
- `IDEMPOTENCY_MODE` (`shared_required` for AWS prod, `local_only` only for
  explicit local/single-process operation)
- `FILE_TRANSFER_CACHE_ENABLED` (`true` when
  `IDEMPOTENCY_MODE=shared_required`)
- `FILE_TRANSFER_CACHE_SECURITY_GROUP_EXPORT_NAME` (required when
  `FILE_TRANSFER_CACHE_ENABLED=true`)
- `FILE_TRANSFER_CACHE_URL_SECRET_ARN` (required when
  `IDEMPOTENCY_MODE=shared_required`; injects runtime `CACHE_REDIS_URL` from
  the secret JSON key `url`)
- `FILE_TRANSFER_BUCKET_BASE_NAME` (required by the canonical runtime
  deployment script; the actual bucket name is derived from the S3 stack output)

Runtime container note:

- `CACHE_REDIS_URL` remains the runtime environment requirement when
  `IDEMPOTENCY_MODE=shared_required`; the ECS service stack satisfies it by
  injecting the value from `FILE_TRANSFER_CACHE_URL_SECRET_ARN`.
- The canonical runtime deployment path is
  `scripts/release/deploy-runtime-cloudformation-environment.sh`, which
  hard-codes the final-release posture:
  `AssignPublicIp=DISABLED`, `IdempotencyMode=shared_required`, and
  `FileTransferCacheEnabled=true`.

For public ALB deployments, record the runtime cluster output:

- `PublicAlbWebAclArn`

See:
`deploy-runtime-cloudformation-environments-guide.md`

### Worker stack parameter contract

Capture these worker-specific values before deploying
`infra/runtime/file_transfer/worker.yml`:

- `WORKER_SERVICE_NAME`
- `JOBS_QUEUE_ARN`
- `JOBS_QUEUE_URL`
- `JOBS_REGION`
- `JOBS_API_BASE_URL`
- `JOBS_WORKER_UPDATE_TOKEN_SECRET_ARN`
- `FILE_TRANSFER_BUCKET_NAME`
- `KMS_ALIAS`
- `IMPORT_KMS_KEY_ARN` (optional; required when the environment imports the
  shared runtime KMS key)
- `WORKER_DESIRED_COUNT`
- `WORKER_MIN_TASK_COUNT`
- `WORKER_MAX_TASK_COUNT`
- `WORKER_SCALE_OUT_QUEUE_DEPTH_TARGET`
- `WORKER_SCALE_OUT_QUEUE_AGE_SECONDS_TARGET`
- `WORKER_SCALE_IN_COOLDOWN_SECONDS`
- `WORKER_SCALE_OUT_COOLDOWN_SECONDS`
- `JOBS_SQS_MAX_NUMBER_OF_MESSAGES`
- `JOBS_SQS_WAIT_TIME_SECONDS`
- `JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS`

Worker contract notes:

- `JOBS_API_BASE_URL` must target the canonical `/v1/*` runtime and is passed
  to the task as `JOBS_API_BASE_URL`.
- `JOBS_WORKER_UPDATE_TOKEN_SECRET_ARN` must resolve to the secret used for
  `JOBS_WORKER_UPDATE_TOKEN`; the worker stack always requires it, including
  scale-from-zero deployments.
- `JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS` must be sized to cover worker
  processing plus the internal result callback path.
- Worker tasks intentionally run with `IDEMPOTENCY_ENABLED=false` and
  `IDEMPOTENCY_MODE=local_only`; do not wire shared-cache idempotency secrets
  into `infra/runtime/file_transfer/worker.yml`.
- The packaged worker command is `nova-file-worker`; there is no active
  `src/worker.py` operator contract.
- `WORKER_SCALE_OUT_QUEUE_DEPTH_TARGET` is the sustained-backlog scale-out
  threshold for queue-depth alarms; the canonical default is `100`.
- Queue-depth bootstrap scale-out uses a fixed `>= 1` visible-message
  threshold, and surge scale-out uses a fixed `>= 500` threshold.
- `WORKER_SCALE_OUT_QUEUE_AGE_SECONDS_TARGET` is the queue-age operator alarm
  threshold; it is not a direct autoscaling target.

## CloudFormation stack names and outputs

Default stack names:

- `${project}-${application}-nova-foundation`
- `${project}-${application}-nova-iam-roles`
- `${project}-${application}-nova-codebuild-release`
- `${project}-${application}-nova-ci-cd`
- `${project}-ci-dev-service-base-url`
- `${project}-ci-prod-service-base-url`
- `${project}-${application}-nova-auth-dev`
- `${project}-${application}-nova-auth-prod`

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
- `EcsInfrastructureRoleForLoadBalancersArn`
- `ReleaseValidationReadRoleArn` (when `RELEASE_VALIDATION_TRUSTED_PRINCIPAL_ARN`
  is configured)
- `PublicAlbWebAclArn` (runtime cluster stack when ALB is internet-facing)

## CodeBuild environment contract

Release build project requires:

- `CODEARTIFACT_DOMAIN`
- `CODEARTIFACT_REPOSITORY` (release build publish target)
- `ECR_REPOSITORY_URI` or `ECR_REPOSITORY_NAME`
- `FILE_DOCKERFILE_PATH`
- `AUTH_DOCKERFILE_PATH`
- `DOCKER_BUILD_CONTEXT`

Publish/promote workflow contracts additionally require:

- `CODEARTIFACT_STAGING_REPOSITORY`
- `CODEARTIFACT_PROD_REPOSITORY`

## Repo-local npm auth helper

For local developer shells, Nova npm auth is repo-scoped rather than global:

```bash
cd /home/bjorn/repos/work/infra-stack/nova
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
repositories. CI workflows may still use it because runners are ephemeral.

Exported variables:

- `FILE_IMAGE_DIGEST`
- `AUTH_IMAGE_DIGEST`
- `PUBLISHED_PACKAGES`
- `RELEASE_MANIFEST_SHA256`
- `CHANGED_UNITS`

`RELEASE_MANIFEST_SHA256` and workflow `manifest_sha256` must represent the
actual SHA256 of `docs/plan/release/RELEASE-VERSION-MANIFEST.md`.

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
`docs/plan/release/RELEASE-VERSION-MANIFEST.md`. If the value is read from
`codeartifact-gate-report.json`, treat that report as a carrier of the
canonical manifest digest rather than the authority itself.
`promotion_candidates_json` may now include both PyPI and npm candidates; npm
entries keep the package scope in `package` and the bare scope name in
`namespace`.

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
- `${DEV_AUTH_BASE_URL}/v1/health/live`
- `${DEV_AUTH_BASE_URL}/v1/health/ready`
- `${DEV_AUTH_BASE_URL}/v1/token/verify`
- `${DEV_AUTH_BASE_URL}/v1/token/introspect`
- `${PROD_AUTH_BASE_URL}/v1/health/live`
- `${PROD_AUTH_BASE_URL}/v1/health/ready`
- `${PROD_AUTH_BASE_URL}/v1/token/verify`
- `${PROD_AUTH_BASE_URL}/v1/token/introspect`

Route namespace policy:

- Canonical consumer capability namespace is `/v1/*`.
- Release validation inputs MUST include canonical file-service `/v1/*` +
  `/metrics/summary` checks, auth-service `/v1/token/*` checks, and required
  legacy-route `404` assertions.
- Legacy route literals are allowed only in dedicated validation `404` checks
  (`validation_legacy_404_paths`), not as active runtime routes.

## References

- Publish packages workflow:
  <https://github.com/3M-Cloud/nova/blob/main/.github/workflows/publish-packages.yml>
- Build/publish image workflow:
  <https://github.com/3M-Cloud/nova/blob/main/.github/workflows/build-and-publish-image.yml>
- Promote prod workflow:
  <https://github.com/3M-Cloud/nova/blob/main/.github/workflows/promote-prod.yml>
- CodeBuild environment variable types:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-codebuild-project-environmentvariable.html>
