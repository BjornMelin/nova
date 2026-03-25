# Implementation status matrix

Status: Active
Last reviewed: 2026-03-25

Use this file to keep current-baseline truth and target-state direction separate.

| Area | Current implemented baseline | Approved target state | Primary docs |
| --- | --- | --- | --- |
| Public auth | mixed / auth-service-era seams still present | bearer JWT only | `docs/architecture/adr/ADR-0034-*`, `docs/architecture/spec/SPEC-0027-*` |
| Async contract | generic jobs | explicit export workflows | `ADR-0035`, `SPEC-0028` |
| Internal async completion | callback-style worker path | workflow-native state, no callback route | `ADR-0035`, `SPEC-0028` |
| Idempotency/state | Redis still in correctness path | DynamoDB, explicit expiration filtering, optional local hot cache only | `ADR-0036`, `SPEC-0029` |
| AWS runtime | ECS/Fargate + ALB + SQS worker | HTTP API + Lambda Web Adapter + Step Functions Standard | `ADR-0033`, `SPEC-0029` |
| SDK layout | split file/auth packages, bespoke TS runtime glue | one package per language, Hey API / openapi-python-client / httr2 | `ADR-0037`, `SPEC-0030`, `docs/clients/CLIENT-SDK-CANONICAL-PACKAGES.md` |
| Docs authority | wide, partially contradictory, wave-1 drift present | small active set, wave-1 archived/superseded | `ADR-0038`, `SPEC-0031`, `docs/overview/ACTIVE-DOCS-INDEX.md` |
| Operations | current provisioning/release runbooks are still authoritative for live systems | serverless runbook is target-state only until migration lands | `docs/runbooks/README.md`, `docs/runbooks/RUNBOOK-SERVERLESS-OPERATIONS.md` |

## Rule

If a branch merges and changes one of these rows, update this matrix in the same
change set.
