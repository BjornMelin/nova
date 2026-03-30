# Runbook — canonical serverless operations

> **Implementation state:** Active operational runbook for the canonical serverless baseline.

## Core runtime

- API Gateway REST API (regional) behind one canonical custom domain
- Lambda (FastAPI via native handler, zip-packaged API runtime)
- Step Functions Standard
- DynamoDB
- S3
- AWS WAF attached to the API stage
- CloudWatch / X-Ray / OpenTelemetry-compatible telemetry

## Public ingress rules

- The custom domain is the only intended public base URL for the runtime.
- The default `execute-api` endpoint is disabled and is not an operator-facing
  invoke path.
- CloudFront is not part of the API ingress path.

## Health model

- API health is control-plane readiness only.
- Export processing health is measured via Step Functions success/failure metrics and backlog alarms.
- DynamoDB throttling, Lambda errors, and Step Functions failure rates are first-class alarms.

## Primary alarms

- API 5xx rate
- API p95/p99 latency
- Lambda error rate / throttles / duration
- Step Functions failed executions
- Step Functions timed-out executions
- DynamoDB throttles
- S3 transfer failures
- DLQ depth if used on event fan-out edges

## Operational defaults

- arm64 for Lambda unless blocked
- reserved concurrency for blast-radius control
- provisioned concurrency only after measuring need
- API Gateway stage access/execution logging enabled for ingress diagnostics
- app-level authorization remains the source of truth
