# Breaking changes v2

> **Implementation state:** Approved hard-cut change record for the wave-2 program.

This file records the intentional hard cuts in the second green-field program.

## Public API

- Delete same-origin/session auth completely.
- Delete `X-Session-Id` and any body `session_id`.
- Delete `X-Scope-Id`.
- Delete any auth-service verification endpoints from the supported external surface.
- Delete legacy remote-auth mode settings and auth-service routing inputs.
- Delete generic job enqueue/read/update routes from the public surface.
- Replace generic jobs with explicit export workflow resources.

## Internal API

- Delete `/v1/internal/jobs/{job_id}/result`.
- Delete worker callback semantics.

## Runtime/infrastructure

- Delete Redis as a required runtime dependency.
- Replace ECS/worker-first target architecture with HTTP API + Lambda + Step Functions as the canonical AWS deployment shape.

## SDK/package layout

- Delete auth SDK packages.
- Delete the dedicated auth service package family.
- Rename file-only SDK packages to unified Nova SDK package names.
- Delete `@nova/sdk-fetch`.

## Docs/governance

- Archive or delete historical, non-canonical planning material from active authority.
