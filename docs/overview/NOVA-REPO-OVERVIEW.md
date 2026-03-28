# Nova repository overview

Status: Active orientation doc
Last reviewed: 2026-03-25

## Purpose

Give new readers a fast mental model of the repository **without** pretending
that every legacy asset has already been retired.

## One-sentence summary

Nova is currently a mixed-wave-2 transfer and export-workflow control-plane
monorepo with bearer-only auth, DynamoDB-backed idempotency, consolidated SDK
packages, and serverless platform components already landed, while some
ECS-era assets remain in-tree as non-canonical leftovers.

## Current implemented baseline

The current baseline now centers:

- transfer APIs plus explicit export workflows
- bearer JWT only, verified in-process in the main API
- DynamoDB-backed idempotency with explicit expiration filtering
- HTTP API + Lambda Web Adapter + Step Functions Standard platform components
- unified SDK packages for TypeScript, Python, and R
- legacy ECS/Fargate + ALB + SQS worker assets retained only as non-canonical leftovers

## Approved target-state program

The target state moves Nova to:

- full retirement of legacy ECS-era assets and duplicate docs surfaces
- one fully canonical serverless control-plane posture across docs, runbooks,
  and implementation
- no residual pre-wave-2 package, auth, or idempotency assumptions in active
  operator or developer docs

## Where to read next

- `IMPLEMENTATION-STATUS-MATRIX.md`
- `CANONICAL-TARGET-2026-04.md`
- `../architecture/README.md`
- `../plan/GREENFIELD-WAVE-2-EXECUTION.md`
