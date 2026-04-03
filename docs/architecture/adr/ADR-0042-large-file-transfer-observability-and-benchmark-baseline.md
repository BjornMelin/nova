---
ADR: 0042
Title: Large-file transfer observability and benchmark baseline
Status: Accepted
Version: 1.0
Date: 2026-04-03
Related:
  - "[ADR-0033: Canonical serverless platform](./ADR-0033-canonical-serverless-platform.md)"
  - "[ADR-0035: Replace generic jobs with export workflows](./ADR-0035-replace-generic-jobs-with-export-workflows.md)"
  - "[ADR-0009: Observability stack](./ADR-0009-observability-analytics-emf-dynamodb-cloudwatch.md)"
  - "[SPEC-0002: S3 integration](../spec/SPEC-0002-s3-integration.md)"
  - "[SPEC-0003: Observability](../spec/SPEC-0003-observability.md)"
  - "[SPEC-0005: Abuse prevention and quotas](../spec/SPEC-0005-abuse-prevention-and-quotas.md)"
References:
  - "[Amazon S3 multipart upload limits](https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html)"
  - "[Amazon S3 Storage Lens metrics and dimensions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-lens-cloudwatch-metrics-dimensions.html)"
  - "[Amazon S3 Storage Lens metrics glossary](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens_metrics_glossary.html)"
  - "[AWS Lambda Power Tuning](https://github.com/alexcasalboni/aws-lambda-power-tuning)"
---

## Summary

Adopt an observability and benchmark baseline before any large-file contract or
workflow changes. This baseline adds benchmark harnesses, export-stage timing
metrics, and a runtime observability dashboard so later transfer-scaling work
is measured against current Nova behavior instead of inferred from static code
review alone.

## Context

- Nova already uses the correct direct-to-S3 data-plane shape for large
  uploads, but the current browser batching defaults and inline export-copy
  tuning are still only lightly measured.
- The repo needed a committed, durable record of the current operating
  baseline before policy, upload-session, quota, or export-copy changes land.
- The current runtime stack already owns alarms and operational outputs in
  `infra/nova_cdk`, and the runtime already emits low-cardinality EMF metrics.
- The biggest immediate risk is changing transfer policy or export execution
  without a shared baseline for `500 GiB` single-upload behavior, `1 TiB`
  aggregate burst expectations, and the current export-copy handler’s
  orchestration cost.

## Alternatives

- A: Land the transfer baseline now with benchmark scripts, dashboard IaC, and
  docs, but keep public API and workflow behavior unchanged.
- B: Ship policy/session/runtime changes before baseline benchmarking and
  dashboard coverage exist.
- C: Keep the transfer-scaling plan as prose only and defer scripts, dashboard
  IaC, and observability updates until a later feature branch.

## Decision Framework

### Option Scoring

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| **A** | **9.3** | **9.2** | **9.4** | **9.1** | **9.28** |
| B | 8.4 | 8.9 | 7.8 | 8.8 | 8.39 |
| C | 6.8 | 7.4 | 8.8 | 6.9 | 7.43 |

`weighted total = (leverage * 0.35) + (value * 0.30) + (maintenance * 0.25) + (adaptability * 0.10)`

## Decision

Choose option A: ship an explicit transfer baseline before the repo changes
transfer policy resolution, upload-session state, quota enforcement, or the
export-copy execution model.

Implementation commitments:

- Add repeatable benchmark scripts for transfer control-plane throughput, inline
  export-copy orchestration, and current browser multipart batching behavior.
- Add active operational documentation for the current 500 GiB single-upload
  plan, 1 TiB aggregate burst plan, benchmark commands, and accepted alarm
  gaps.
- Add runtime dashboard IaC and export-stage age metrics that expose the
  current transfer/export baseline without changing the public API contract.

## Related Requirements

- [FR-0007](../requirements.md#fr-0007-observability-and-analytics)
- [FR-0009](../requirements.md#fr-0009-s3-multipart-correctness-and-acceleration-compatibility)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
- [NFR-0003](../requirements.md#nfr-0003-operability)

## Consequences

1. Positive outcomes: Nova gets benchmarkable, reviewable evidence before the
   higher-risk transfer/session/export changes begin.
2. Trade-offs/costs: the baseline adds scripts and dashboard IaC without
   delivering end-user throughput gains by itself.
3. Ongoing considerations: Storage Lens publishing and later alarm expansion
   still depend on future transfer-scaling work; the operations runbook must
   document those accepted gaps explicitly.

## Changelog

- 2026-04-03: Accepted the transfer observability and benchmark baseline and
  recorded the benchmark/dashboard/doc commitments.

---

## ADR Completion Checklist

- [x] All placeholders (`<…>`) and bracketed guidance are removed/replaced.
- [x] All links are markdown-clickable and resolve to valid local docs or sources.
- [x] Context includes concrete constraints, not generic boilerplate.
- [x] Alternatives are decision-relevant and scored consistently.
- [x] Winning row is bold and matches the Decision section.
- [x] Accepted/Implemented ADR score is `>= 9.0`.
- [x] Related requirements link to exact requirement anchors.
- [x] Consequences include both benefits and trade-offs.
