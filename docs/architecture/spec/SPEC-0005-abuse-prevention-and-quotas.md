---
Spec: 0005
Title: Abuse Prevention and Quotas
Status: Active
Version: 1.1
Date: 2026-02-11
Related:
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0003: Observability](./SPEC-0003-observability.md)"
References:
  - "[AWS WAF rate-based rules](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html)"
  - "[S3 lifecycle for aborting incomplete multipart uploads](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html)"
---

## 1. Problem statement

Control-plane endpoints are cheap individually but can be abused to:

- generate excessive presigned URLs,
- create high volumes of uncompleted multipart uploads,
- increase storage and request costs.

## 2. Control strategy

### 2.1 Rate limiting

Primary control SHOULD be infrastructure-level:

- AWS WAF rate-based rules on `/api/file-transfer/*`.

Secondary control MAY be app-level throttling for defense in depth.

### 2.2 Quotas

Per-scope quotas (phase target):

- maximum active multipart uploads
- maximum total bytes initiated per window (hour/day)
- maximum `sign-parts` calls per upload/session

### 2.3 Cleanup and cost containment

- Rely on S3 lifecycle abort rules for incomplete multipart uploads.
- Optionally run periodic janitor workflows for stale business-level records.

## 3. Operational observability

Abuse controls SHOULD emit:

- rate-limit hit counters,
- quota-rejection counters by reason,
- scope-level trend metrics for anomaly detection.

## 4. Acceptance criteria

- Limits are configurable per environment.
- Rejections are observable in logs and metrics.
- Controls do not break nominal upload/download flows under expected traffic.

## 5. Traceability

- [FR-0009](../requirements.md#fr-0009-s3-multipart-correctness-and-acceleration-compatibility)
- [FR-0007](../requirements.md#fr-0007-observability-and-analytics)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
