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
- Lambda (FastAPI via the repo-owned Lambda entrypoint, Mangum-backed, zip-packaged, Python 3.13, arm64)
- Step Functions Standard
- DynamoDB
- S3
- CloudWatch / tracing

## IaC

- CDK v2 in Python under `infra/nova_cdk`
- public API Lambda artifact built by release automation and consumed through
  explicit artifact coordinates in CDK
- runtime deployment publishes `deploy-output.json` / `deploy-output.sha256`
  as the only downstream authority for the custom-domain base URL and release
  provenance

## Network/security

- no public application subnets required for the control plane
- use IAM roles and temporary credentials everywhere
- secrets/config in Secrets Manager / Parameter Store
- KMS encryption at rest
- WAF and stage logging at the API Gateway ingress
- disable the default `execute-api` endpoint and publish only the custom-domain
  base URL
- bearer JWT verification remains in-process in the application
- browser CORS remains an explicit allowed-origins contract across API and S3
  browser flows

## Operational defaults

- reserved concurrency for blast radius in production and standard-quota
  environments; reduced-quota non-prod accounts may intentionally omit
  reservations at deploy time
- provisioned concurrency only when justified by measured latency
- structured JSON logs
- correlation IDs
- RED metrics + saturation + workflow failure metrics
- post-deploy validation must prove release identity, readiness, protected
  auth behavior, browser CORS preflight, and legacy-path 404 drift against the
  deploy-output artifact
