---
Spec: 0005
Title: Abuse Prevention and Quotas
Status: Active
Version: 1.5
Date: 2026-04-03
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0016: v1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[SPEC-0029: Canonical serverless platform](./SPEC-0029-platform-serverless.md)"
  - "[requirements.md](../requirements.md)"
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

- AWS WAF rate-based rules on `/v1/transfers/*` and `/v1/exports*`.
- Worker result persistence does not traverse the public HTTP surface and is
  therefore outside the WAF-managed route family entirely.

Secondary control MAY be app-level throttling for defense in depth.

### 2.2 Quotas

Per-scope quotas:

- maximum active multipart uploads
- maximum total bytes initiated per day
- maximum `sign-parts` calls per upload/session

The runtime enforces these limits before issuing new multipart work and returns
deterministic `429` responses when a scope exceeds the configured envelope.
Transfer policy defaults remain environment-bounded, and AppConfig can narrow
the effective limits without changing the deployed runtime artifact.

### 2.3 Cleanup and cost containment

- Rely on S3 lifecycle abort rules for incomplete multipart uploads.
- Run a scheduled janitor to settle expired multipart sessions, retry stale
  aborts, and abort orphaned multipart uploads under both upload and export
  prefixes.

## 3. Operational observability

Abuse controls SHOULD emit:

- rate-limit hit counters,
- quota-rejection counters by reason,
- stale-session reconciliation counters,
- incomplete multipart upload footprint alarms sourced from S3 Storage Lens,
- scope-level trend metrics for anomaly detection.

## 4. Acceptance criteria

- Limits are configurable per environment.
- Rejections are observable in logs and metrics.
- Expired multipart sessions settle without waiting for DynamoDB TTL deletion.
- Controls do not break nominal upload/download flows under expected traffic.

## 5. Traceability

- [FR-0009](../requirements.md#fr-0009-s3-multipart-correctness-and-acceleration-compatibility)
- [FR-0007](../requirements.md#fr-0007-observability-and-analytics)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
