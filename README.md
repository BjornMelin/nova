# aws-file-transfer-api (Docs Bundle)

This directory contains a **repo-scoped** documentation set for the deployable
FastAPI-based File Transfer API service.

The service implements a stable control-plane API for:

- presigned single PUT uploads
- presigned multipart uploads (initiate/sign-parts/complete/abort)
- presigned downloads

It is designed to be deployed via container-craft as a **sidecar service** per app
and routed under the same origin at `/api/file-transfer/*`.

**Bundle generated:** 2026-02-11

## Key upstream constraints (AWS)

- Multipart upload limits: max 10,000 parts; part size 5 MiB–5 GiB; object size bound by part constraints. citeturn4view0
- Bucket CORS must expose headers (including `ETag`) to browser clients. citeturn6view0
- Abort incomplete multipart uploads should be managed via lifecycle. citeturn1search1
- Transfer Acceleration requires DNS-compliant bucket names without periods and uses the accelerate endpoint. citeturn5view0

## Documentation map

- `PRD.md`
- `docs/architecture/requirements.md`
- `docs/architecture/adr/`
- `docs/architecture/spec/`
- `docs/plan/PLAN.md`
- `docs/plan/subplans/`
