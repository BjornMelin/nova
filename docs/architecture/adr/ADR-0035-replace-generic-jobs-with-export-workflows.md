# ADR-0035 -- Replace generic jobs with export workflows

> **Implementation state:** Implemented in the current repository baseline, with only legacy references and retirement cleanup still pending.

## Status
Accepted

## Decision

Keep the generic jobs public API removed and use explicit export workflow
resources with typed state transitions as the active contract.

## Context

The current repository already exposes explicit export workflow resources and
no longer depends on an internal callback route for active API behavior, but
legacy references still need to stay retired.

## Why this wins

- clearer client contract
- better generated SDKs
- easier state modelling and troubleshooting
- simpler persistence model
- removes fake abstraction

## Consequences

- keep generic jobs routes and models out of the active public contract
- keep `/v1/internal/jobs/{job_id}/result` retired from active behavior
- keep orchestration-native state transitions as the canonical lifecycle
- keep the Dash async-path aligned to export workflows rather than a stringly
  typed job name seam
