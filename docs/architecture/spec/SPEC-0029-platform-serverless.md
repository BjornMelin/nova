# SPEC-0029 -- Canonical serverless platform

> **Implementation state:** Implemented in-repo for the active canonical baseline.

## Runtime

- CloudFront + WAF
- API Gateway HTTP API
- Lambda (FastAPI via Lambda Web Adapter, Python 3.13, arm64)
- Step Functions Standard
- DynamoDB
- S3
- CloudWatch / tracing

## IaC

- CDK v2 in Python under `infra/nova_cdk`

## Network/security

- no public application subnets required for the control plane
- use IAM roles and temporary credentials everywhere
- secrets/config in Secrets Manager / Parameter Store
- KMS encryption at rest
- route-level JWT authorizers in API Gateway where valuable

## Operational defaults

- reserved concurrency for blast radius
- provisioned concurrency only when justified by measured latency
- structured JSON logs
- correlation IDs
- RED metrics + saturation + workflow failure metrics
