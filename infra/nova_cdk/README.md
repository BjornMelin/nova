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
  -c certificate_arn=arn:aws:acm:us-west-2:111111111111:certificate/00000000-0000-0000-0000-000000000000 \
  -c jwt_issuer=https://issuer.example.com/ \
  -c jwt_audience=api://nova \
  -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json
npx aws-cdk diff \
  -c account=111111111111 \
  -c region=us-west-2 \
  -c api_domain_name=api.dev.example.com \
  -c certificate_arn=arn:aws:acm:us-west-2:111111111111:certificate/00000000-0000-0000-0000-000000000000 \
  -c jwt_issuer=https://issuer.example.com/ \
  -c jwt_audience=api://nova \
  -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json
npx aws-cdk deploy \
  -c account=111111111111 \
  -c region=us-west-2 \
  -c api_domain_name=api.dev.example.com \
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
- Configure `allowed_origins` via CDK context or `STACK_ALLOWED_ORIGINS` for
  production deployments; local and dev stacks default to `*`.
- The stack exports one canonical `NovaPublicBaseUrl`, which always points at
  the configured custom domain.
