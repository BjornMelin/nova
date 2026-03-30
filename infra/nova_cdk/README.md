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

- Provide `-c account=... -c region=...` or set
  `CDK_DEFAULT_ACCOUNT`/`CDK_DEFAULT_REGION` before synth or deploy.
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
  `api_stage_throttling_rate_limit`,
  `api_stage_throttling_burst_limit`,
  and `waf_rate_limit`.
- The API Lambda defaults to no reserved concurrency outside prod and `25` in
  prod unless `api_reserved_concurrency`/`API_RESERVED_CONCURRENCY` is set
  explicitly.
- The stack exports one canonical `NovaPublicBaseUrl`, which always points at
  the configured custom domain.
