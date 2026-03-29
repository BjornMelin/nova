# Canonical target state (2026-04)

> **Implementation state:** Approved target-state overview. It describes where Nova is going, not what is fully implemented today.


## System summary

Nova becomes a small control-plane API for direct-to-S3 transfer flows plus durable export orchestration.

## Canonical public responsibilities

- issue upload intents and multipart part URLs
- finalize uploads
- create exports
- read export status/results
- list export history
- issue download URLs / metadata as appropriate

## Canonical non-responsibilities

- no dedicated auth service
- no session or same-origin auth contract
- no generic jobs API
- no internal worker callback route
- no Redis dependency
- no public auth SDK split

## Target package layout

- `packages/nova_file_api` — the public FastAPI control-plane API
- `packages/nova_workflows` — Step Functions task handlers and orchestration logic
- `packages/nova_runtime_support` — shared middleware, errors, settings, telemetry helpers
- `packages/nova_dash_bridge` — async-first Dash/browser helpers only
- `packages/nova_sdk_ts` — generated TS SDK
- `packages/nova_sdk_py` — generated Python SDK
- `packages/nova_sdk_r` — thin httr2 R client
- `infra/nova_cdk` — canonical IaC

## Canonical AWS topology

```text
Browser / Dash / TS / Python / R clients
        |
 API Gateway REST API + WAF (regional stage association)
        |
 Lambda (FastAPI via Lambda Web Adapter, arm64, Python 3.13, bearer auth in-process)
        |
  DynamoDB + S3 + Step Functions Standard + CloudWatch + X-Ray/OTel
        |
  Lambda task handlers in packages/nova_workflows
```

## Key design laws

1. Public contracts are explicit and typed.
2. Auth is bearer JWT only.
3. Async workflows are explicit export resources, not generic jobs.
4. DynamoDB is the durable state system of record.
5. S3 does the heavy byte movement.
6. The API owns coordination, not long-running transfer work.
7. SDKs are generated or extremely thin.
8. Docs authority stays intentionally small.
