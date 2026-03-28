# Runbook — canonical serverless operations

> **Implementation state:** Target-state operational runbook. Do not use it as the current production runbook until the platform migration lands.


## Core runtime

- API Gateway HTTP API
- Lambda (FastAPI via Lambda Web Adapter)
- Step Functions Standard
- DynamoDB
- S3
- CloudFront + WAF
- CloudWatch / X-Ray / OpenTelemetry-compatible telemetry

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
- route-level JWT authorizers in API Gateway where it reduces noise before the app
- app-level authorization remains the source of truth
