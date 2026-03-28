# ADR-0035 -- Replace generic jobs with export workflows

> **Implementation state:** Approved target-state ADR. The current codebase still exposes generic jobs and callback-style workflow seams; this ADR defines their replacement.

## Status
Accepted

## Decision

Delete the generic jobs public API and replace it with explicit export workflow resources and typed state transitions.

## Context

The attached repo still exposes a general `job_type` + payload API even though the worker effectively supports a single real workload pattern. The worker also posts results back through an internal callback route.

## Why this wins

- clearer client contract
- better generated SDKs
- easier state modelling and troubleshooting
- simpler persistence model
- removes fake abstraction

## Consequences

- delete generic jobs routes and models from the public contract
- delete `/v1/internal/jobs/{job_id}/result`
- replace worker callback lifecycle with orchestration-native state transitions
- fix the Dash async-path bug by removing the stringly-typed job name seam
