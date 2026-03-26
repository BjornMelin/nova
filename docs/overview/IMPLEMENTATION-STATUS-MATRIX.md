# Implementation status matrix

Status: Active
Last reviewed: 2026-03-25

Use this file to keep current-baseline truth and target-state direction separate.

| Area | Current implemented baseline | Approved target state | Primary docs |
| --- | --- | --- | --- |
| Public auth | bearer JWT only, verified in-process | bearer JWT only | `docs/architecture/adr/ADR-0034-*`, `docs/architecture/spec/SPEC-0027-*` |
| Transport / OpenAPI expression | shared pure-ASGI request context, centralized FastAPI exception registration, native route-declared OpenAPI responses, no file-API schema post-processor | same shape retained while broader wave-2 API/platform work continues | `docs/architecture/spec/SPEC-0027-*`, `docs/architecture/adr/superseded/ADR-0041-*`, `README.md` |
| Bridge/public surface | `nova_file_api.public` is async-first; FastAPI consumes it directly through `nova_dash_bridge.AsyncFileTransferService` with async auth resolution and async-capable S3 clients; retained sync adapters stay isolated to true sync hosts such as Flask/Dash | same async-first surface retained while broader wave-2 API/platform work continues | `README.md`, `docs/clients/README.md`, `docs/architecture/spec/SPEC-0017-*`, `docs/architecture/spec/SPEC-0019-*` |
| Async contract | explicit export workflows | explicit export workflows | `ADR-0035`, `SPEC-0028` |
| Internal async completion | workflow-native state, no callback route | workflow-native state, no callback route | `ADR-0035`, `SPEC-0028` |
| Idempotency/state | Redis still in correctness path | DynamoDB, explicit expiration filtering, optional local hot cache only | `ADR-0036`, `SPEC-0029` |
| AWS runtime | ECS/Fargate + ALB + SQS worker | HTTP API + Lambda Web Adapter + Step Functions Standard | `ADR-0033`, `SPEC-0029` |
| SDK layout | file-only package names remain, bespoke TS runtime glue remains | one package per language, Hey API / openapi-python-client / httr2 | `ADR-0037`, `SPEC-0030`, `docs/clients/CLIENT-SDK-CANONICAL-PACKAGES.md` |
| Docs authority | wide, partially contradictory, wave-1 drift present | small active set, wave-1 archived/superseded | `ADR-0038`, `SPEC-0031`, `docs/overview/ACTIVE-DOCS-INDEX.md` |
| Operations | current provisioning/release runbooks are still authoritative for live systems | serverless runbook is target-state only until migration lands | `docs/runbooks/README.md`, `docs/runbooks/RUNBOOK-SERVERLESS-OPERATIONS.md` |

## Rule

If a branch merges and changes one of these rows, update this matrix in the same
change set.
