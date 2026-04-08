# nova-cdk

Canonical CDK v2 Python app for the Nova serverless runtime, release-support
IAM roles, and the optional AWS-native release control plane.

## Local commands

From the repository root, use the canonical repo-native verification shape:

```bash
uv sync --locked --all-packages --all-extras --dev
uv run pytest -q -m runtime_gate
uv run pytest -q -m "not runtime_gate and not generated_smoke"
uv run pytest -q -m generated_smoke
npx aws-cdk@2.1117.0 synth --app "uv run --package nova-cdk python infra/nova_cdk/app.py" \
  -c account=111111111111 \
  -c region=us-west-2 \
  -c api_domain_name=api.dev.example.com \
  -c hosted_zone_id=Z1234567890EXAMPLE \
  -c hosted_zone_name=example.com \
  -c api_lambda_artifact_bucket=nova-ci-artifacts-111111111111-us-east-1 \
  -c api_lambda_artifact_key=runtime/nova-file-api/example/example/nova-file-api-lambda.zip \
  -c api_lambda_artifact_sha256=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
  -c workflow_lambda_artifact_bucket=nova-ci-artifacts-111111111111-us-east-1 \
  -c workflow_lambda_artifact_key=runtime/nova-workflows/example/example/nova-workflows-lambda.zip \
  -c workflow_lambda_artifact_sha256=fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210 \
  -c certificate_arn=arn:aws:acm:us-west-2:111111111111:certificate/00000000-0000-0000-0000-000000000000 \
  -c jwt_issuer=https://issuer.example.com/ \
  -c jwt_audience=api://nova \
  -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json
```

If you want manual CDK CLI commands after the repo-wide sync, run:

```bash
cd infra/nova_cdk
npx aws-cdk synth \
  -c account=111111111111 \
  -c region=us-west-2 \
  -c api_domain_name=api.dev.example.com \
  -c hosted_zone_id=Z1234567890EXAMPLE \
  -c hosted_zone_name=example.com \
  -c api_lambda_artifact_bucket=nova-ci-artifacts-111111111111-us-east-1 \
  -c api_lambda_artifact_key=runtime/nova-file-api/example/example/nova-file-api-lambda.zip \
  -c api_lambda_artifact_sha256=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
  -c workflow_lambda_artifact_bucket=nova-ci-artifacts-111111111111-us-east-1 \
  -c workflow_lambda_artifact_key=runtime/nova-workflows/example/example/nova-workflows-lambda.zip \
  -c workflow_lambda_artifact_sha256=fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210 \
  -c certificate_arn=arn:aws:acm:us-west-2:111111111111:certificate/00000000-0000-0000-0000-000000000000 \
  -c jwt_issuer=https://issuer.example.com/ \
  -c jwt_audience=api://nova \
  -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json
npx aws-cdk diff \
  -c account=111111111111 \
  -c region=us-west-2 \
  -c api_domain_name=api.dev.example.com \
  -c hosted_zone_id=Z1234567890EXAMPLE \
  -c hosted_zone_name=example.com \
  -c api_lambda_artifact_bucket=nova-ci-artifacts-111111111111-us-east-1 \
  -c api_lambda_artifact_key=runtime/nova-file-api/example/example/nova-file-api-lambda.zip \
  -c api_lambda_artifact_sha256=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
  -c workflow_lambda_artifact_bucket=nova-ci-artifacts-111111111111-us-east-1 \
  -c workflow_lambda_artifact_key=runtime/nova-workflows/example/example/nova-workflows-lambda.zip \
  -c workflow_lambda_artifact_sha256=fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210 \
  -c certificate_arn=arn:aws:acm:us-west-2:111111111111:certificate/00000000-0000-0000-0000-000000000000 \
  -c jwt_issuer=https://issuer.example.com/ \
  -c jwt_audience=api://nova \
  -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json
npx aws-cdk deploy \
  -c account=111111111111 \
  -c region=us-west-2 \
  -c api_domain_name=api.dev.example.com \
  -c hosted_zone_id=Z1234567890EXAMPLE \
  -c hosted_zone_name=example.com \
  -c api_lambda_artifact_bucket=nova-ci-artifacts-111111111111-us-east-1 \
  -c api_lambda_artifact_key=runtime/nova-file-api/example/example/nova-file-api-lambda.zip \
  -c api_lambda_artifact_sha256=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
  -c workflow_lambda_artifact_bucket=nova-ci-artifacts-111111111111-us-east-1 \
  -c workflow_lambda_artifact_key=runtime/nova-workflows/example/example/nova-workflows-lambda.zip \
  -c workflow_lambda_artifact_sha256=fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210 \
  -c certificate_arn=arn:aws:acm:us-west-2:111111111111:certificate/00000000-0000-0000-0000-000000000000 \
  -c jwt_issuer=https://issuer.example.com/ \
  -c jwt_audience=api://nova \
  -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json
```

For synth-only verification without the CDK CLI, run the app directly:

```bash
cd infra/nova_cdk
CDK_DEFAULT_ACCOUNT=111111111111 \
CDK_DEFAULT_REGION=us-west-2 \
ENVIRONMENT=dev \
JWT_ISSUER=https://issuer.example.com/ \
JWT_AUDIENCE=api://nova \
JWT_JWKS_URL=https://issuer.example.com/.well-known/jwks.json \
API_DOMAIN_NAME=api.dev.example.com \
HOSTED_ZONE_ID=Z1234567890EXAMPLE \
HOSTED_ZONE_NAME=example.com \
API_LAMBDA_ARTIFACT_BUCKET=nova-ci-artifacts-111111111111-us-east-1 \
API_LAMBDA_ARTIFACT_KEY=runtime/nova-file-api/example/example/nova-file-api-lambda.zip \
API_LAMBDA_ARTIFACT_SHA256=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
WORKFLOW_LAMBDA_ARTIFACT_BUCKET=nova-ci-artifacts-111111111111-us-east-1 \
WORKFLOW_LAMBDA_ARTIFACT_KEY=runtime/nova-workflows/example/example/nova-workflows-lambda.zip \
WORKFLOW_LAMBDA_ARTIFACT_SHA256=fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210 \
CERTIFICATE_ARN=arn:aws:acm:us-west-2:111111111111:certificate/00000000-0000-0000-0000-000000000000 \
uv run --package nova-cdk python app.py
```

## Configuration

- For synth, diff, and deploy, either `cd infra/nova_cdk` and pass
  `-c account=… -c region=…` to `npx aws-cdk`, or set
  `CDK_DEFAULT_ACCOUNT`/`CDK_DEFAULT_REGION` before running synth/diff/deploy.
- Provide `jwt_issuer`, `jwt_audience`, and `jwt_jwks_url` for every synth,
  diff, and deploy. The serverless runtime is bearer-JWT-only and fails
  closed on incomplete OIDC verifier wiring.
- Provide `api_domain_name` and `certificate_arn` for every synth, diff, and
  deploy. The canonical public ingress is one Regional REST API custom domain,
  and the default `execute-api` endpoint stays disabled.
- Provide `hosted_zone_id` and `hosted_zone_name` for every runtime synth,
  diff, and deploy so the stack can create the Route 53 alias record for the
  canonical API custom domain.
- Provide `api_lambda_artifact_bucket`, `api_lambda_artifact_key`, and
  `api_lambda_artifact_sha256` for every synth, diff, and deploy. CDK consumes
  an immutable API Lambda zip artifact from the release pipeline and no longer
  builds the API package locally at synth time.
- Provide `workflow_lambda_artifact_bucket`, `workflow_lambda_artifact_key`,
  and `workflow_lambda_artifact_sha256` for every synth, diff, and deploy. CDK
  consumes one immutable workflow Lambda zip artifact for all Step Functions
  task handlers.
- The API Lambda continues to use `Code.fromBucket()` without `objectVersion`.
  This is intentional: Nova treats the immutable artifact key plus
  `api_lambda_artifact_sha256` and deploy-output provenance as the source of
  truth, and the scoped CDK warning is acknowledged at the app level.
- When `release_github_owner`, `release_github_repo`, and
  `release_connection_arn` are provided through CDK context or environment,
  the app also synthesizes the release stacks. By default it creates
  `NovaReleaseSupportStack` first and then `NovaReleaseControlPlaneStack`.
- Release-only bootstrap can synthesize `NovaReleaseSupportStack` without
  `hosted_zone_id`. In that mode the default execution roles omit Route 53
  hosted-zone permissions until the support stack is redeployed with
  `HOSTED_ZONE_ID` / `hosted_zone_id`, or until explicit equivalent execution
  role ARNs are supplied to the release control plane.
- Runtime-only synth/diff/deploy must not require release-control inputs.
  If `RELEASE_CONNECTION_ARN` is absent, the CDK app should synthesize only
  the runtime stack path even when runtime deploy artifacts and runtime stack
  ids are present.
  The support stack provisions:
  - one CloudFormation execution role for the dev runtime stack
  - one CloudFormation execution role for the prod runtime stack
  - both roles are trusted only by `cloudformation.amazonaws.com`
  - both roles attach a curated runtime-service policy set (CloudFormation,
    API Gateway, Lambda, Step Functions, DynamoDB, S3, SNS, SQS, AppConfig,
    budgets, CloudWatch, Route 53, logs, EventBridge, WAF) plus scoped IAM
    role-management actions for Nova runtime roles
  - if `DEV_RUNTIME_CFN_EXECUTION_ROLE_ARN` and
    `PROD_RUNTIME_CFN_EXECUTION_ROLE_ARN` are both provided explicitly, the app
    skips `NovaReleaseSupportStack` and uses those role ARNs directly
  - `NovaReleaseControlPlaneStack` then provisions:
  - one imported GitHub CodeConnections source ARN
  - one CodePipeline with `ValidateReleasePrep`, `PublishAndDeployDev`,
    `ApproveProd`, and `PromoteAndDeployProd` stages
  - one release artifact bucket and one release manifest bucket
  - CodeBuild projects that publish internal packages to CodeArtifact and
    deploy the runtime from the merged release commit SHA
- The release control plane now expects:
  - `RELEASE_CONNECTION_ARN`
  - `DEV_RUNTIME_CONFIG_PARAMETER_NAME`
  - `DEV_RUNTIME_STACK_ID`
  - `PROD_RUNTIME_CONFIG_PARAMETER_NAME`
  - `PROD_RUNTIME_STACK_ID`
  instead of duplicating per-environment domain, certificate, hosted-zone, JWT,
  CORS values, and extra runtime deploy-role hops across many
  release-control-plane inputs.
- Configure `allowed_origins` via CDK context or `STACK_ALLOWED_ORIGINS` for
  production deployments; non-prod stacks default to `*`.
- When you pass `STACK_ALLOWED_ORIGINS` through the environment, provide a JSON
  array string such as `["https://app.example.com"]` or `["*"]`.
- Configure `enable_waf` / `ENABLE_WAF` when you need to override the ingress
  default. Production defaults to `true` and fails closed if set to `false`.
  Non-production defaults to `false` to avoid unnecessary steady-state WAF
  cost.
- `scripts.release.export_runtime_stack_config_env` now exports structured SSM
  runtime-config values as JSON so the CodeBuild release path can pass
  `STACK_ALLOWED_ORIGINS` and `ENABLE_WAF` back into the CDK runtime parser
  without Python-repr drift.
- `scripts.release.prepare_release_pr` is the canonical local entrypoint for
  generating committed release-prep artifacts under `release/**`.
- The primary and only supported release executor is the
  `NovaReleaseControlPlaneStack` CodePipeline, which deploys the configured
  runtime stack ids from the merged release commit SHA and its S3-backed
  release execution manifest.
- The active machine-readable contract sources for runtime deploy and
  post-deploy validation are `docs/contracts/deploy-output-authority-v2.schema.json`
  and `docs/contracts/workflow-post-deploy-validate.schema.json`.
- Post-deploy validation should consume `deploy-output.json`, not a manually
  entered base URL. The deploy-output artifact binds the release commit SHA,
  runtime version, `NovaPublicBaseUrl`, stack name, region, and stack outputs
  for incident response and revalidation.
- The authoritative stack outputs captured in `deploy-output.json` now include
  the transfer-policy AppConfig ids, upload/session quota table names, export
  copy part table name, observability dashboard name, Storage Lens
  configuration id, and transfer spend budget name in addition to the
  existing ingress, alarm-topic, workflow, and log-group outputs.
- Optional ingress safeguard overrides:
  `enable_waf`,
  `enable_reserved_concurrency`,
  `api_reserved_concurrency`,
  `workflow_reserved_concurrency`,
  `api_stage_throttling_rate_limit`,
  `api_stage_throttling_burst_limit`,
  `waf_rate_limit`,
  and `waf_write_rate_limit`.
- Reserved concurrency defaults are intentionally bounded when enabled: the API
  Lambda uses `5` outside prod and `25` in prod, and each workflow task Lambda
  uses `2` outside prod and `10` in prod unless the corresponding context/env
  override is set explicitly.
- The canonical deployed Lambda env surface, workflow handler inventory, and
  validator-facing function-group authority live in
  `infra/nova_cdk/src/nova_cdk/runtime_release_manifest.py`. Keep
  `runtime_stack.py`, `scripts/release/runtime_config_contract.py`, and
  `scripts/release/validate_runtime_release.py` derived from that module rather
  than re-stating literals in multiple places.
- `enable_reserved_concurrency` / `ENABLE_RESERVED_CONCURRENCY` defaults to
  `true`. Production deploys fail closed if it is set to `false`.
- Manual low-quota non-prod deploys should set
  `ENABLE_RESERVED_CONCURRENCY=false` explicitly before running
  `npx aws-cdk deploy`.
- Manual non-prod ingress hardening checks can set `ENABLE_WAF=true`
  explicitly before running `npx aws-cdk deploy`.
- The transfer bucket aborts incomplete multipart uploads after 7 days and
  expires transient `tmp/` objects after 3 days. Durable `exports/` objects
  are retained. The bucket also has S3 Transfer Acceleration enabled, but the
  runtime policy keeps acceleration disabled unless an allow-listed profile
  turns it on for presigned upload requests.
- The runtime stack now provisions:
  - `UploadSessionsTable` for durable multipart session state, including
    authoritative upload-id alias items on the base table for strong
    multipart continuation reads
  - `TransferUsageTable` for quota accounting
  - `ExportCopyPartsTable` for durable worker-lane multipart copy state with
    TTL cleanup on `expires_at_epoch`
  - one SQS queue plus DLQ for queued export multipart copy work
  - one AppConfig application/environment/profile/deployment for the transfer
    policy document
  - one hourly reconciliation Lambda schedule for stale multipart uploads
  - one S3 Storage Lens configuration with CloudWatch publishing enabled
  - one monthly transfer budget routed to `NovaAlarmTopicArn`
- The Regional REST ingress emits JSON access logs to
  `/aws/apigateway/nova-rest-api-access-{stage}` with 90-day retention.
- When WAF is enabled, it writes logs to `aws-waf-logs-nova-rest-api-{stage}`
  with 90-day retention.
- When WAF is enabled, it uses AWS managed IP-reputation/common/bad-inputs rule
  groups plus two rate rules: a general per-IP ceiling (`waf_rate_limit`,
  default `2000` over 5 minutes) and a stricter write-path ceiling
  (`waf_write_rate_limit`, default `500` over 5 minutes) scoped to
  `/v1/exports` and `/v1/transfers/uploads`.
- The stack always exports `NovaAlarmTopicArn` and
  `NovaApiAccessLogGroupName`. It exports `NovaWafLogGroupName` only when WAF
  is enabled. All runtime alarms publish to the SNS topic
  `nova-runtime-alarms-{environment}`. Operators can set
  `alarm_notification_emails` / `ALARM_NOTIFICATION_EMAILS` to create email
  subscriptions at deploy time, or attach PagerDuty, Chatbot, and EventBridge
  fan-out without changing the stack.
- The stack also exports:
  - `NovaUploadSessionsTableName`
  - `NovaTransferUsageTableName`
  - `NovaExportCopyPartsTableName`
  - `NovaTransferPolicyAppConfigApplicationId`
  - `NovaTransferPolicyAppConfigEnvironmentId`
  - `NovaTransferPolicyAppConfigProfileId`
- Multipart upload-session continuation reads use an authoritative upload-id
  alias row in the base table, so request-path lookups stay strongly
  consistent without any GSI dependency.
- The transfer policy document now covers:
  - policy-scoped acceleration enablement
  - checksum mode (`none`, `optional`, `required`)
  - the large-export worker threshold
- The observability surface now includes queued export copy alarms for worker
  DLQ depth and queue age in addition to the existing transfer and workflow
  alarms.
- When WAF is enabled, logs redact the `Authorization` and `Cookie` headers
  before delivery to CloudWatch Logs and keep only `BLOCK` / `COUNT`
  decisions to concentrate the security signal.
- The stack exports one canonical `NovaPublicBaseUrl`, which always points at
  the configured custom domain.
- The first production custom-domain cutover may temporarily use
  `allowed_origins=["*"]`; GitHub issue `#111` tracks tightening that allowlist
  after the initial cutover.
