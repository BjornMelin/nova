---
Spec: 0003
Title: Observability
Status: Active
Version: 1.1
Date: 2026-02-11
Related:
  - "[ADR-0001: ECS/Fargate behind ALB](../adr/ADR-0001-deployment-on-ecs-fargate-behind-alb.md)"
References:
  - "[OpenTelemetry specification](https://opentelemetry.io/docs/specs/)"
  - "[FastAPI deployment concepts](https://fastapi.tiangolo.com/deployment/concepts/)"
---

## 1. Health endpoints

Service MUST expose:

- `GET /healthz` as the canonical service health endpoint.
- `GET /` returning `200` for ALB/platform compatibility where root-path health checks are required.

Health responses SHOULD include minimal metadata (service name, version, and status).

## 2. Logging requirements

Structured logs MUST include:

- `request_id`
- event name (`initiate`, `sign_parts`, `complete`, `abort`, `presign_download`)
- status (`success` or `failure`)
- safe key context (prefix/scope-safe value only)

Sensitive data controls:

- presigned URLs MUST NOT be logged.
- query strings and signatures MUST be redacted.
- auth headers/tokens MUST never be emitted to logs.

## 3. Metrics requirements

Phase 1 minimum:

- request counters by endpoint and status class
- latency histogram per endpoint
- error counters by error code

Phase 2 target:

- multipart part-sign count distribution
- active multipart upload gauge by scope
- upstream S3 API failure counters

## 4. Correlation and debugging

- Each response error envelope MUST include `request_id`.
- Logs SHOULD include optional `scope_id` where safe and non-sensitive.
- Deployment rollouts SHOULD emit startup/version events to support incident triage.

## 5. Traceability

- [NFR-0000](../requirements.md#nfr-0000-observability)
- [NFR-FT-005](../requirements.md#nfr-ft-005-observability)
