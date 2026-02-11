---
Spec: 0000
Title: HTTP API Contract
Status: Active
Version: 1.1
Date: 2026-02-11
Related:
  - "[ADR-0000: FastAPI service decision](../adr/ADR-0000-fastapi-microservice.md)"
  - "[ADR-0002: OpenAPI as contract and SDK generation](../adr/ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[SPEC-0001: Security model](./SPEC-0001-security-model.md)"
  - "[SPEC-0002: S3 integration](./SPEC-0002-s3-integration.md)"
References:
  - "[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)"
  - "[FastAPI metadata and OpenAPI docs](https://fastapi.tiangolo.com/tutorial/metadata/)"
---

## 1. Scope

Defines the external control-plane API for upload/download orchestration. This API does
not transfer file bytes; it returns presigned URLs and coordinates multipart lifecycle.

## 2. Base path

- Base path: `/api/file-transfer`
- Content type: `application/json`

## 3. Endpoints

### 3.1 POST `/uploads/initiate`

Purpose: choose upload strategy and return single PUT URL or multipart upload context.

Request fields:

- `filename`: string, required
- `content_type`: string or `null`
- `size_bytes`: integer, required
- `session_id`: string, optional in same-origin mode, required when auth context is absent

Response (single strategy):

- `strategy`: `"single"`
- `bucket`: string
- `key`: string
- `url`: string (presigned PUT URL)
- `expires_in_seconds`: integer

Response (multipart strategy):

- `strategy`: `"multipart"`
- `bucket`: string
- `key`: string
- `upload_id`: string
- `part_size_bytes`: integer
- `expires_in_seconds`: integer

### 3.2 POST `/uploads/sign-parts`

Purpose: sign one or more multipart part numbers for an existing upload.

Request fields:

- `key`: string, required
- `upload_id`: string, required
- `part_numbers`: integer array, required
- `session_id`: string, optional/required by auth mode

Response fields:

- `urls`: object map of `part_number -> presigned_url`
- `expires_in_seconds`: integer

### 3.3 POST `/uploads/complete`

Purpose: finalize multipart upload.

Request fields:

- `key`: string, required
- `upload_id`: string, required
- `parts`: array of `{ part_number, etag }`, required
- `session_id`: string, optional/required by auth mode

Response fields:

- `bucket`: string
- `key`: string
- `etag`: string or `null`
- `version_id`: string or `null` (when bucket versioning is enabled)

### 3.4 POST `/uploads/abort`

Purpose: abort a multipart upload and release incomplete parts.

Request fields:

- `key`: string, required
- `upload_id`: string, required
- `session_id`: string, optional/required by auth mode

Response fields:

- `ok`: boolean

### 3.5 POST `/downloads/presign`

Purpose: issue a presigned GET URL for an existing object.

Request fields:

- `key`: string, required
- `session_id`: string, optional/required by auth mode
- `content_disposition`: string, optional
- `filename`: string, optional

Response fields:

- `bucket`: string
- `key`: string
- `url`: string (presigned GET URL)
- `expires_in_seconds`: integer

## 4. Contract rules

- Keys are server-generated; callers cannot select arbitrary storage keys.
- `upload_id` and `key` pairs MUST belong to caller scope.
- Strategy selection (single vs multipart) SHOULD be based on configured multipart
  threshold and size validations.

## 5. Error model

All errors MUST return:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {},
    "request_id": "string"
  }
}
```

Recommended domain error codes:

- `invalid_request`
- `unauthorized`
- `forbidden`
- `not_found`
- `conflict`
- `upstream_s3_error`
- `internal_error`

## 6. Traceability

- [FR-0000](../requirements.md#fr-0000-control-plane-endpoints)
- [FR-0001](../requirements.md#fr-0001-s3-multipart-correctness)
- [FR-0002](../requirements.md#fr-0002-key-generation-and-scoping)
- [FR-0004](../requirements.md#fr-0004-auth-and-authorization-pluggable)
