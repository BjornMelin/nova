# Breaking changes v2

> **Implementation state:** Approved hard-cut change record for the wave-2 program.

This file records the intentional hard cuts in the second green-field program.

## Authority / references

- `../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `../architecture/spec/superseded/SPEC-0000-http-api-contract.md`
- `../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `../architecture/spec/SPEC-0027-public-api-v2.md`
- `../architecture/requirements.md`
- `../plan/GREENFIELD-WAVE-2-EXECUTION.md`

## Public API

- Delete same-origin/session auth completely.
- Delete `X-Session-Id` and any body `session_id`.
- Delete `X-Scope-Id`.
- Delete any auth-service verification endpoints from the supported external surface.
- Delete generic job enqueue/read/update routes from the public surface.
- Replace generic jobs with explicit export workflow resources.

## Internal API

- Delete `/v1/internal/jobs/{job_id}/result`.
- Delete worker callback semantics.

## Runtime/infrastructure

- Delete Redis as a required runtime dependency.
- Replace ECS/worker-first target architecture with Regional REST API + direct Regional WAF + the repo-owned Lambda entrypoint + Step Functions as the canonical AWS deployment shape.

## SDK/package layout

- Delete auth SDK packages.
- Rename file-only SDK packages to unified Nova SDK package names.
- Delete `@nova/sdk-fetch`.

## Docs/governance

- Archive or delete historical, non-canonical planning material from active authority.
