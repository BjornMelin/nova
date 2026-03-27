# nova-cdk

Canonical CDK v2 Python app for the Nova serverless runtime.

## Local commands

```bash
cd infra/nova_cdk
uv run --package nova-cdk cdk synth \
  -c jwt_issuer=https://issuer.example.com/ \
  -c jwt_audience=api://nova \
  -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json
uv run --package nova-cdk cdk diff \
  -c jwt_issuer=https://issuer.example.com/ \
  -c jwt_audience=api://nova \
  -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json
uv run --package nova-cdk cdk deploy \
  -c jwt_issuer=https://issuer.example.com/ \
  -c jwt_audience=api://nova \
  -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json
```

## Configuration

- Provide `-c account=... -c region=...` or set
  `CDK_DEFAULT_ACCOUNT`/`CDK_DEFAULT_REGION` before synth or deploy.
- Use `region=us-east-1`; CloudFront WAF resources are regional there and the
  stack fails closed if synthesized for any other region.
- Provide `jwt_issuer`, `jwt_audience`, and `jwt_jwks_url` for every synth,
  diff, and deploy. The serverless runtime is bearer-JWT-only and fails
  closed on incomplete OIDC verifier wiring.
- Configure `allowed_origins` via CDK context or `STACK_ALLOWED_ORIGINS` for
  production deployments; local and dev stacks default to `*`.
- API Gateway keeps `/v1/health/live` and `/v1/health/ready` public for
  release probes even when the rest of `/v1` is JWT-authorized.
