---
Spec: 0002
Title: S3 Integration
Status: Active
Version: 1.1
Date: 2026-02-11
Related:
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
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
[SPEC-0000](./SPEC-0000-http-api-contract.md)).

## 2. Strategy selection

- Service SHOULD select single PUT for objects below configured multipart threshold.
- Service MUST select multipart strategy for larger uploads.
- Threshold and part size MUST be configurable through environment contract.

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

## 6. Traceability

- [FR-0001](../requirements.md#fr-0001-s3-multipart-correctness)
- [FR-0003](../requirements.md#fr-0003-transfer-acceleration-support)
- [NFR-FT-004](../requirements.md#nfr-ft-004-reliability-and-cleanup)
