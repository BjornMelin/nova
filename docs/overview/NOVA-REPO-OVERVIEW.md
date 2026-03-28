# Nova repository overview

Status: Active orientation doc
Last reviewed: 2026-03-25

## Purpose

Give new readers a fast mental model of the repository **without** pretending
that the approved target-state program has already landed.

## One-sentence summary

Nova is currently a transfer-control and async-jobs monorepo on an older
ECS/SQS/Redis/auth-service-oriented baseline, with an approved wave-2 program
that will hard-cut it into a smaller bearer-only transfer + export-workflow
control plane.

## Current implemented baseline

The current baseline still centers:

- transfer APIs plus generic jobs
- dedicated auth-service-era artifacts
- ECS/Fargate + ALB + SQS worker topology
- Redis in correctness/idempotency paths
- split SDK/package layout

## Approved target-state program

The target state moves Nova to:

- bearer JWT only
- explicit export workflows
- API Gateway HTTP API + Lambda Web Adapter + Step Functions Standard
- DynamoDB + S3 as the durable core
- one canonical SDK package per language
- much smaller docs authority

## Where to read next

- `IMPLEMENTATION-STATUS-MATRIX.md`
- `CANONICAL-TARGET-2026-04.md`
- `../architecture/README.md`
- `../plan/GREENFIELD-WAVE-2-EXECUTION.md`
