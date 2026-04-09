---
Spec: 0002
Title: S3 Integration
Status: Active
Version: 1.4
Date: 2026-04-08
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0016: v1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[SPEC-0027: Public API v2](./SPEC-0027-public-api-v2.md)"
  - "[requirements.md](../requirements.md)"
References:
  - "[Amazon S3 multipart upload overview](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)"
  - "[Amazon S3 multipart upload limits](https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html)"
  - "[Amazon S3 CORS configuration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/cors.html)"
  - "[Amazon S3 Transfer Acceleration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/transfer-acceleration.html)"
---

## 1. Multipart correctness

Service behavior MUST enforce AWS multipart constraints:

- max parts: 10,000
- part size: 5 MiB to 5 GiB (except last part may be smaller)
- complete request MUST include per-part `ETag` values

Validation failures should return contract error envelopes consistent with
[SPEC-0027](./SPEC-0027-public-api-v2.md).

## 2. Strategy selection

- Service SHOULD select single PUT for objects below configured multipart threshold.
- Service MUST select multipart strategy for larger uploads.
- Threshold and part size MUST be configurable through environment contract.
- Default runtime posture MUST set `FILE_TRANSFER_MAX_UPLOAD_BYTES` to
  `536_870_912_000` (`500 GiB`).
- Default runtime posture MUST set `FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS`
  to `1800`.
- Clients MUST use progressive `sign-parts` requests rather than wide-batch URL
  presigning. The canonical default batch rule is `max(64, 4 * maxConcurrency)`
  unless a smaller client override is configured.
- Service MUST expose `POST /v1/transfers/uploads/introspect` so clients can
  list already-uploaded parts and resume multipart uploads without restarting
  from part `1`.
- `POST /v1/transfers/uploads/initiate` MAY accept additive policy-selection
  hints such as `workload_class`, `policy_hint`, and
  `checksum_preference`.
- `GET /v1/capabilities/transfers` MUST expose the current effective transfer
  policy envelope, including acceleration, checksum mode, quota limits, and the
  large-export worker threshold.

## 3. Browser CORS requirements

The bucket CORS policy MUST allow:

- allowed origins matching application domains,
- methods required for upload/download flows,
- exposed `ETag` header for multipart completion.

## 4. Transfer Acceleration

Transfer Acceleration MUST remain opt-in through the effective transfer policy
envelope. When `accelerate_enabled=true` for the caller:

- SDK clients MUST use accelerate endpoint mode.
- Bucket naming MUST be DNS-compliant and avoid periods.
- Bucket acceleration MUST be enabled in AWS configuration.

## 5. Lifecycle and cleanup

- Bucket lifecycle MUST abort incomplete multipart uploads after configured age.
- Temporary prefixes SHOULD have expiration lifecycle policies where appropriate.

## 6. Export copy behavior

- Export-copy flows MAY use `CopyObject` only for source objects `<= 5 GB`.
- Export-copy flows for larger source objects MUST use multipart copy
  (`CreateMultipartUpload`, `UploadPartCopy`, `CompleteMultipartUpload`) and
  MUST abort the multipart copy on failure.
- Moderate export copies MAY remain inline inside the export workflow task
  runtime.
- Larger server-side copies MUST use the internal queued worker lane with
  durable part state, canonical SQS message attributes for poison recovery,
  normal retry/DLQ handling for unattributable malformed messages, and
  idempotent part-copy workers.

## 7. Checksum behavior

- The effective transfer policy MUST expose both `checksum_algorithm` and
  `checksum_mode`.
- `checksum_mode=none` means the runtime does not require checksum input.
- `checksum_mode=optional` means clients MAY provide checksums and the runtime
  MUST preserve compatible signing/completion fields when supplied.
- `checksum_mode=required` means clients MUST provide checksum material
  consistent with `checksum_algorithm`:
  - single-part uploads provide the object checksum at initiate time
  - multipart uploads provide per-part checksum material during signing and
    completion
- The current canonical checksum algorithm is `SHA256` when checksums are
  enabled.

## 8. Traceability

- [FR-0009](../requirements.md#fr-0009-s3-multipart-correctness-and-acceleration-compatibility)
- [IR-0004](../requirements.md#ir-0004-browser-compatibility-for-multipart-workflows)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
