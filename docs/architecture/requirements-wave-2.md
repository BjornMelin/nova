# Requirements -- wave 2 canonical Nova

Status: Historical reference
Last archived: 2026-04-10

> **Implementation state:** Historical target-state requirement set retained for traceability. It is not active current-state authority.

## Product requirements

- support direct browser/Dash uploads to S3 via presigned and multipart flows
- support durable async export workflows
- support Python, TypeScript, and R client apps against one public contract
- support bearer JWT auth only
- keep the API control-plane focused; do not proxy large byte streams through the API

## Architecture requirements

- no dedicated auth service
- no Redis dependency
- no generic jobs public API
- no worker callback route
- one canonical AWS deployment target
- one canonical SDK package per language

## Repo requirements

- smaller active docs authority set
- smaller release/generation script surface
- smaller package surface
- easier onboarding for client-app developers

## Quality requirements

- typed request/response models
- explicit error schema
- deterministic tests
- async correctness on the request path
- strong observability in the target platform
