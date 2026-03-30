# nova-cdk

Canonical CDK v2 Python app for the Nova serverless runtime.

## Local commands

If you have the AWS CDK CLI installed, run:

```bash
cd infra/nova_cdk
npx aws-cdk synth \
  -c account=111111111111 \
  -c region=us-west-2 \
  -c api_domain_name=api.dev.example.com \
  -c api_lambda_artifact_bucket=nova-ci-artifacts-111111111111-us-east-1 \
  -c api_lambda_artifact_key=runtime/nova-file-api/example/example/nova-file-api-lambda.zip \
  -c api_lambda_artifact_sha256=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
  -c certificate_arn=arn:aws:acm:us-west-2:111111111111:certificate/00000000-0000-0000-0000-000000000000 \
  -c jwt_issuer=https://issuer.example.com/ \
  -c jwt_audience=api://nova \
  -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json
npx aws-cdk diff \
  -c account=111111111111 \
  -c region=us-west-2 \
  -c api_domain_name=api.dev.example.com \
  -c api_lambda_artifact_bucket=nova-ci-artifacts-111111111111-us-east-1 \
  -c api_lambda_artifact_key=runtime/nova-file-api/example/example/nova-file-api-lambda.zip \
  -c api_lambda_artifact_sha256=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
  -c certificate_arn=arn:aws:acm:us-west-2:111111111111:certificate/00000000-0000-0000-0000-000000000000 \
  -c jwt_issuer=https://issuer.example.com/ \
  -c jwt_audience=api://nova \
  -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json
npx aws-cdk deploy \
  -c account=111111111111 \
  -c region=us-west-2 \
  -c api_domain_name=api.dev.example.com \
  -c api_lambda_artifact_bucket=nova-ci-artifacts-111111111111-us-east-1 \
  -c api_lambda_artifact_key=runtime/nova-file-api/example/example/nova-file-api-lambda.zip \
  -c api_lambda_artifact_sha256=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
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
- Provide `hosted_zone_id` and `hosted_zone_name` for every synth and deploy so
  the stack can create the Route 53 alias record for the canonical API custom
  domain.
- Provide `api_lambda_artifact_bucket`, `api_lambda_artifact_key`, and
  `api_lambda_artifact_sha256` for every synth, diff, and deploy. CDK consumes
  an immutable API Lambda zip artifact from the release pipeline and no longer
  builds the API package locally at synth time.
- Configure `allowed_origins` via CDK context or `STACK_ALLOWED_ORIGINS` for
  production deployments; local and dev stacks default to `*`.
- `Nova Release Apply` publishes the API Lambda zip to
  `RELEASE_ARTIFACT_BUCKET` under a content-addressed key and writes
  `.artifacts/api-lambda-artifact.json`. Export deploy inputs from that manifest
  with:

```bash
eval "$(uv run python scripts/release/emit_api_lambda_artifact_env.py \
  --manifest-path .artifacts/api-lambda-artifact.json)"
```

- `Deploy Runtime` is the canonical repo-owned deployment entrypoint. It
  consumes `release-apply-artifacts`, deploys `NovaRuntimeStack` through
  `npx aws-cdk deploy`, uses GitHub OIDC plus an explicit CloudFormation
  execution role and the CDK bootstrap publishing roles, and writes
  `deploy-output.json` plus `deploy-output.sha256` as the authoritative
  runtime deploy artifact.
- Post-deploy validation should consume `deploy-output.json`, not a manually
  entered base URL. The deploy-output artifact binds the release commit SHA,
  runtime version, `NovaPublicBaseUrl`, stack name, region, and stack outputs
  for incident response and revalidation.
- Optional ingress safeguard overrides:
  `api_reserved_concurrency`,
  `workflow_reserved_concurrency`,
  `api_stage_throttling_rate_limit`,
  `api_stage_throttling_burst_limit`,
  `waf_rate_limit`,
  and `waf_write_rate_limit`.
- Reserved concurrency defaults are intentionally bounded: the API Lambda uses
  `5` outside prod and `25` in prod, and each workflow task Lambda uses `2`
  outside prod and `10` in prod unless the corresponding context/env override
  is set explicitly.
- The transfer bucket aborts incomplete multipart uploads after 7 days and
  expires transient `tmp/` objects after 3 days. Durable `exports/` objects
  are retained.
- The Regional REST ingress emits JSON access logs to
  `/aws/apigateway/nova-rest-api-access-{stage}` and WAF logs to
  `aws-waf-logs-nova-rest-api-{stage}` with 90-day retention.
- The WAF uses AWS managed IP-reputation/common/bad-inputs rule groups plus two
  rate rules: a general per-IP ceiling (`waf_rate_limit`, default `2000` over
  5 minutes) and a stricter write-path ceiling (`waf_write_rate_limit`,
  default `500` over 5 minutes) scoped to `/v1/exports` and
  `/v1/transfers/uploads`.
- The stack exports `NovaAlarmTopicArn`, `NovaApiAccessLogGroupName`, and
  `NovaWafLogGroupName`; all runtime alarms publish to the SNS topic
  `nova-runtime-alarms-{environment}`. Operators can set
  `alarm_notification_emails` / `ALARM_NOTIFICATION_EMAILS` to create email
  subscriptions at deploy time, or attach PagerDuty, Chatbot, and EventBridge
  fan-out without changing the stack.
- WAF logs redact the `Authorization` and `Cookie` headers before delivery to
  CloudWatch Logs and keep only `BLOCK` / `COUNT` decisions to concentrate the
  security signal.
- The stack exports one canonical `NovaPublicBaseUrl`, which always points at
  the configured custom domain.
