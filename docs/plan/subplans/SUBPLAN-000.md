# SUBPLAN-000: Create FastAPI skeleton + core endpoints (no auth yet)

## Goal

Implement the HTTP contract and make local dev functional with env-based config.

## Steps

1. Create `src/...` package with FastAPI app factory.
2. Implement endpoints:
   - initiate, sign-parts, complete, abort, presign download
3. Add `/healthz`.
4. Implement service layer by importing/using `aws_dash_s3_file_handler.FileTransferService`
   or equivalent internal module.
5. Add unit tests.

## Exit criteria

- Local `uv run` starts the service and `/openapi.json` is correct.
