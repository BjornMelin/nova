# PLAN: End-to-end File Transfer API on AWS (container-craft + FastAPI + Dash clients)

## 0. Executive summary

We will deliver a production-grade File Transfer API that supports:

- direct-to-S3 uploads/downloads using presigned URLs (single and multipart)
- optional S3 Transfer Acceleration in dev + prod
- clean integration with container-craft (per-service bucket, least-priv IAM, env injection)
- OpenAPI schema enabling multi-language clients (Dash, R Shiny, Next.js)

We will NOT stream file bytes through ECS/ALB. The API is control-plane only.

## 1. Baseline inventory (current state)

### 1.1 container-craft

- Provides per-service file-transfer bucket via `infra/file_transfer/s3.yml`
  - CORS includes exposed headers default `ETag`
  - lifecycle includes abort incomplete multipart uploads
  - optional transfer acceleration parameter
- Injects canonical `FILE_TRANSFER_*` env vars into ECS tasks when enabled.
- File-transfer stack is gated by:
  - run ∈ {deploy-new-service, deploy-file-transfer}
  - file_transfer_enabled == "true"

### 1.2 aws-dash-s3-handler library

- Canonical env contract matches container-craft, including FILE_TRANSFER_USE_ACCELERATE_ENDPOINT.
- Provides Flask + FastAPI integration primitives.

### 1.3 Dash apps (e.g., pca-analysis-dash)

- Already integrates via package-backed file transfer modules.

## 2. Target architecture

### 2.1 Logical diagram

Clients (browser, Next.js, Shiny)
  |
  | 1) POST /api/file-transfer/uploads/initiate  (auth required)
  v
File Transfer API (FastAPI on ECS behind ALB)
  |
  | 2) S3 CreateMultipartUpload / Presign URLs / CompleteMultipartUpload
  v
S3 File Transfer Bucket (per-service, SSE-KMS, CORS, lifecycle, optional acceleration)

Data plane:

- Client uploads parts directly to S3 via presigned URLs.
Control plane:
- API signs URLs + calls multipart control APIs.

## 3. Key invariants and constraints

- S3 presigned URLs are limited by IAM principal permissions and expire quickly.
- Multipart completion requires ETag for each uploaded part.
- S3 CORS must allow explicit origins and must expose ETag.
- If Transfer Acceleration enabled:
  - bucket must have acceleration enabled
  - presigned URLs must use accelerate endpoint
  - bucket name must not contain periods

## 4. AWS infrastructure and configuration

### 4.1 S3 bucket (per service)

Use container-craft file-transfer stack:

- EnableTransferAcceleration: true (dev + prod)
- CorsAllowedOrigins: explicit origins (ServiceDNS only for dev/prod)
- CorsExposedHeaders: ETag
- AbortIncompleteMultipartUploadDays: 7 (default ok)
- SSE-KMS + Bucket Key enabled

### 4.2 ECS service

Deploy the File Transfer API as a standard ECS service via container-craft:

- DockerContainerPort: 8080
- Health check: GET / returns 200
- Task role: least-priv S3 + KMS (provided by container-craft when file_transfer_enabled true)
- Secrets:
  - use ECS secrets for auth config / signing secrets as required
  - ensure Fargate platform version >= 1.4.0 if extracting JSON keys into env vars

### 4.3 Auth

- Validate JWT in the API service
- Enforce scope-based authorization:
  - file:upload
  - file:download

## 5. Repo layout (final shape)

We will keep platform and service separate (KISS boundary).

### 5.1 container-craft (platform)

Add docs + example configs only (no new stacks required):

- docs/how-to/fastapi-service.md
- docs/how-to/deploy-file-transfer-api.md
- configs/examples/file-transfer-api.dev.yml
- configs/examples/file-transfer-api.prod.yml

### 5.2 aws-dash-s3-handler (library)

Minor updates if needed:

- ensure FastAPI router/app creation is stable and documented for deployment
- ensure accelerate endpoint behavior is covered in tests

### 5.3 NEW repo: file-transfer-api-service (deployable container)

- FastAPI app using aws-dash-s3-handler core
- Dockerfile
- GitHub actions using container-craft@v3:
  - deploy-ecs-cluster (once)
  - deploy-new-service
  - build-and-push-docker
  - deploy-ecs

## 6. Implementation phases

### Phase 1 — container-craft docs/config hardening

- Add FastAPI deployment how-to
- Add file-transfer API deployment how-to
- Add example service configs (dev/prod)
- Optional: renderer validation for bucket naming when acceleration enabled

### Phase 2 — Build deployable File Transfer API service repo

- Implement FastAPI app:
  - GET / (health)
  - /api/file-transfer endpoints per architecture SPECs
  - JWT validation + scope checks
  - boto3 client configured with use_accelerate_endpoint when enabled
- Add Dockerfile + uv/ruff/mypy CI
- Add integration tests (local) for:
  - env parsing
  - key prefix enforcement
  - multipart happy path (mocked)

### Phase 3 — Deploy dev environment

- Deploy ECS cluster baseline (if needed)
- Deploy file-transfer-api service infra (deploy-new-service)
- Push image + deploy
- Validate:
  - CORS preflight
  - multipart upload with browser test
  - complete multipart (ETag captured)
  - accelerate endpoint usage

### Phase 4 — Client integration (Dash / Next.js / Shiny)

- Provide TypeScript client generation from OpenAPI (openapi-typescript or openapi-generator)
- Provide R client guidance:
  - direct HTTP via httr2
  - optional generated client later
- For Dash:
  - either keep existing in-app endpoints OR switch to calling the standalone API
  - document both patterns

### Phase 5 — Production rollout

- Enable acceleration in prod config
- Confirm CORS origin is only ServiceDNS(s)
- Confirm logs do not contain presigned URLs
- Add alarms/dashboards as needed

## 7. Testing checklist

- Unit:
  - object key generation and sanitization
  - prefix enforcement
  - size-based strategy selection
- Integration:
  - initiate -> sign-parts -> upload parts -> complete
  - abort path
  - presign download with filename disposition
- Operational:
  - rotate secrets and force new deployment to pick up changes
  - verify lifecycle aborts incomplete multipart after configured days

## 8. Risk register

- CORS misconfiguration → Provide “known-good” example configs; document S3 CORS evaluation rules.
- Presigned URL leakage in logs → Redact URLs; log only bucket + prefix + key hash.
- Large-file browser memory issues → multipart with streaming file slicing; no full buffering.

## 9. References (AWS)

- Presigned URL upload:
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html>
- Presigned URL overview:
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html>
- S3 CORS:
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/cors.html>
- Transfer Acceleration:
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/transfer-acceleration-examples.html>
- Multipart overview:
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html>
- UploadPart:
  <https://docs.aws.amazon.com/AmazonS3/latest/API/API_UploadPart.html>
- CompleteMultipartUpload:
  <https://docs.aws.amazon.com/AmazonS3/latest/API/API_CompleteMultipartUpload.html>
- ECS secrets via env vars:
  <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html>
