# SUBPLAN-002: Container image + container-craft deployment integration

## Goal

Build container image and deploy as sidecar service via container-craft.

## Steps

1. Add Dockerfile and production server command (uvicorn workers).
2. Add container-craft config templates for dev/prod.
3. Validate ALB routing: `/api/file-transfer` → sidecar.
4. Validate S3 permissions.

## Exit criteria

- Dev environment supports end-to-end browser upload/download flows.
