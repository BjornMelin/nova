# PRD: Deployable File Transfer API (FastAPI) for container-craft apps

**Date:** 2026-02-11

## 1. Problem

We need a reusable, production-grade API service that provides a stable file transfer
control-plane, so browser clients can upload/download from S3 efficiently without
proxying large payloads through web application containers.

The service must be usable by:

- Dash apps (Python)
- Shiny apps (R)
- Next.js apps (TypeScript)

## 2. Goals

1. Implement the standard `/api/file-transfer` endpoint contract.
2. Support uploads from small to very large objects (multi-GB → 500 GB and beyond),
   subject to app-specific policy settings.
3. Support Transfer Acceleration when enabled in infra and config.
4. Provide strong security boundaries:
   - authenticated access (pluggable; JWT/OIDC recommended)
   - scoped keys and least privilege IAM
5. Provide high-quality, automated API documentation and client SDK generation inputs
   via OpenAPI.

## 3. Non-goals (Phase 1)

- No heavy compute jobs or data processing pipeline.
- No multi-tenant bucket shared across unrelated apps by default (use per-app deployment).

## 4. Success metrics

- Upload and download flows work end-to-end in dev and prod via container-craft.
- OpenAPI schema is stable and published automatically.
- Docs site is updated on merge/release.

## 5. Primary users

- Frontend code in Dash/Shiny/Next.js that needs signed operations.
- Developers maintaining container-craft deployed stacks.
