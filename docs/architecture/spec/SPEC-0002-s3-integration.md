---
Spec: 0002
Title: S3 Integration
Status: Active
Version: 1.2
Date: 2026-03-11
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API contract](./superseded/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: v1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
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

Validation failures should return contract error envelopes (see
[SPEC-0000](./superseded/SPEC-0000-http-api-contract.md)).

## 2. Strategy selection

- Service SHOULD select single PUT for objects below configured multipart threshold.
- Service MUST select multipart strategy for larger uploads.
- Threshold and part size MUST be configurable through environment contract.
- Default runtime posture MUST set `FILE_TRANSFER_MAX_UPLOAD_BYTES` to
  `536_870_912_000` (`500 GiB`).
- Default runtime posture MUST set `FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS`
  to `1800`.
- Clients MUST use progressive `sign-parts` requests rather than wide-batch URL
  presigning. The canonical batch rule is `min(16, 2 * maxConcurrency)` unless
  a smaller client override is configured.
- Service MUST expose `POST /v1/transfers/uploads/introspect` so clients can
  list already-uploaded parts and resume multipart uploads without restarting
  from part `1`.

## 3. Browser CORS requirements

The bucket CORS policy MUST allow:

- allowed origins matching application domains,
- methods required for upload/download flows,
- exposed `ETag` header for multipart completion.

## 4. Transfer Acceleration

When `FILE_TRANSFER_USE_ACCELERATE_ENDPOINT=true`:

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

## 7. Traceability

- [FR-0009](../requirements.md#fr-0009-s3-multipart-correctness-and-acceleration-compatibility)
- [IR-0004](../requirements.md#ir-0004-browser-compatibility-for-multipart-workflows)
- [NFR-0002](../requirements.md#nfr-0002-scalability-and-resilience)
