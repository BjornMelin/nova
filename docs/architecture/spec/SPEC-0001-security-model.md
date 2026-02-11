---
Spec: 0001
Title: Security Model
Status: Active
Version: 1.1
Date: 2026-02-11
Related:
  - "[ADR-0001: ECS/Fargate deployment behind ALB](../adr/ADR-0001-deployment-on-ecs-fargate-behind-alb.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
References:
  - "[S3 presigned URL overview](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)"
  - "[AWS presigned URL best practices](https://docs.aws.amazon.com/prescriptive-guidance/latest/presigned-url-best-practices/overview.html)"
  - "[RFC 6750 Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750)"
---

## 1. Auth modes

### 1.1 Same-origin sidecar mode (recommended default)

- Upstream application handles user authentication.
- Browser calls remain same-origin under `/api/file-transfer`.
- API receives trusted user context through gateway/app integration or session identity.

### 1.2 JWT/OIDC bearer token mode

- API validates bearer JWTs.
- `scope_id` is derived from `sub` or a configured claim.
- Required permissions SHOULD include `file:upload` and `file:download`.

## 2. Authorization rules

- Storage keys MUST be server-generated.
- Every mutation/read operation MUST validate key ownership by `scope_id`.
- Follow-up multipart operations MUST validate:
  - key prefix
  - matching `upload_id`
  - same caller scope as initiation

## 3. Key and scope model

Canonical scope format:

- `{prefix}/{scope_id}/{generated_object_name}`

Allowed prefixes are configured by environment (`uploads/`, `exports/`, `tmp/`).

## 4. Presigned URL safeguards

- Upload/download URLs MUST be short-lived.
- Full presigned URLs MUST NOT be logged.
- Query strings and signatures MUST be excluded from structured logs and error payloads.

## 5. IAM and infra controls

- Task role MUST follow least privilege to bucket and approved prefixes.
- Bucket MUST remain private with Block Public Access enabled.
- Encryption at rest MUST remain enabled through platform-managed settings.

## 6. Threat-focused requirements

- Prevent horizontal access by strict scope-prefix authorization.
- Prevent key injection by rejecting client-selected arbitrary keys.
- Reduce replay window via TTL limits and auditable request IDs.

## 7. Traceability

- [FR-0002](../requirements.md#fr-0002-key-generation-and-scoping)
- [FR-0004](../requirements.md#fr-0004-auth-and-authorization-pluggable)
- [NFR-FT-001](../requirements.md#nfr-ft-001-security-baseline)
- [NFR-FT-002](../requirements.md#nfr-ft-002-iam-least-privilege)
