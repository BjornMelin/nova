---
SPEC: 0029
Title: Canonical serverless platform
Status: Implemented
Version: 1.0
Date: 2026-03-25
Related:
  - "[ADR-0033: Canonical serverless platform](../adr/ADR-0033-canonical-serverless-platform.md)"
---

## Runtime

- API Gateway REST API (regional) with one canonical custom domain
- AWS WAF (regional, API stage association)
- Lambda (FastAPI via native handler, Python 3.13, arm64)
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
- WAF and stage logging at the API Gateway ingress
- disable the default `execute-api` endpoint and publish only the custom-domain
  base URL
- bearer JWT verification remains in-process in the application

## Operational defaults

- reserved concurrency for blast radius
- provisioned concurrency only when justified by measured latency
- structured JSON logs
- correlation IDs
- RED metrics + saturation + workflow failure metrics
