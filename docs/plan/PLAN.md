# PLAN (aws-file-transfer-api): Build + deploy the FastAPI service end-to-end in AWS

**Date:** 2026-02-11

## 0. Executive summary

Create a deployable File Transfer API service implementing the standard control-plane
contract, publish OpenAPI-driven docs, and deploy it via container-craft as a sidecar service.

## 1. Phases

### Phase 1 — Service skeleton and contract

- FastAPI app skeleton
- Pydantic models aligned with the contract
- Service layer reused from `aws-dash-s3-file-handler` where possible

### Phase 2 — Auth + scoping

- Implement pluggable auth verifier and scope resolver
- Default “session_id scope” mode for same-origin deployments

### Phase 3 — Deployment integration

- Container image build
- Container-craft deploy template integration
- `/healthz` and ALB routing verification

### Phase 4 — Documentation + OpenAPI automation

- MkDocs Material site
- Scalar API reference integration
- GH Actions publishing pipeline

## 2. Validation

- unit tests for service logic
- smoke test scripts for upload/download
- dev deployment verification; then prod

## 3. Subplans

- `docs/plan/subplans/SUBPLAN-000.md`
- `docs/plan/subplans/SUBPLAN-001.md`
- `docs/plan/subplans/SUBPLAN-002.md`
- `docs/plan/subplans/SUBPLAN-003.md`
