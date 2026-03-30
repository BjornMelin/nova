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
- The WAF attaches directly to the Regional REST API stage.
- The WAF baseline includes AWS managed IP-reputation, common-rule, and
  known-bad-input rule groups, plus explicit rate-based blocks.
- The default rate ceilings are `2000` requests per IP over 5 minutes for all
  paths and `500` requests per IP over 5 minutes for `/v1/exports` and
  `/v1/transfers/uploads`.

## Health model

- API health is control-plane readiness only.
- Export processing health is measured via Step Functions success/failure metrics and backlog alarms.
- DynamoDB throttling, Lambda errors, and Step Functions failure rates are first-class alarms.
- Runtime alarms publish to the exported `NovaAlarmTopicArn` SNS topic.
- API access logs and WAF logs are also exported via
  `NovaApiAccessLogGroupName` and `NovaWafLogGroupName` for post-deploy
  validation and incident response.

## Primary alarms

- API 5xx rate
- API Lambda throttles
- API p95/p99 latency
- workflow-task Lambda throttles
- Lambda error rate / duration
- Step Functions failed executions
- Step Functions timed-out executions
- DynamoDB throttles
- S3 transfer failures
- DLQ depth if used on event fan-out edges

## Operational defaults

- arm64 for Lambda unless blocked
- reserved concurrency for blast-radius control
- API Lambda reserved concurrency defaults: `5` outside prod, `25` in prod
- workflow task Lambda reserved concurrency defaults: `2` outside prod, `10`
  in prod
- provisioned concurrency only after measuring need
- API Gateway stage access/execution logging enabled for ingress diagnostics
- API access logs are emitted to
  `/aws/apigateway/nova-rest-api-access-{stage}` with 90-day retention
- WAF logs are emitted to `aws-waf-logs-nova-rest-api-{stage}` with 90-day
  retention, redact the `Authorization` and `Cookie` headers, and keep only
  `BLOCK` / `COUNT` actions
- S3 aborts incomplete multipart uploads after 7 days and expires transient
  `tmp/` objects after 3 days; exported artifacts under `exports/` remain
  durable
- Step Functions retries Lambda service exceptions and timeouts explicitly with
  exponential backoff, 30-second max delay, and full jitter before routing to
  deterministic failure persistence
- Operators can attach downstream subscriptions or fan-out targets to the
  exported `NovaAlarmTopicArn` topic (`nova-runtime-alarms-{environment}`)
  without modifying the stack, or set `alarm_notification_emails` /
  `ALARM_NOTIFICATION_EMAILS` to auto-create email subscriptions at deploy time
- app-level authorization remains the source of truth
