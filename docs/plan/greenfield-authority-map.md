# Green-field simplification -- authority ID map

Status: Active routing index
Last updated: 2026-03-19

This table maps the original `.agents/nova_greenfield_codex_pack` identifiers to
canonical Nova ADR/SPEC files under `docs/architecture/`. Use it when tracing
prompts, `manifest.json`, or audit artifacts back to repo authority.

## ADR mapping (pack → canonical)

| Pack ADR | Canonical ADR | Title |
| --- | --- | --- |
| `adr/ADR-0001-single-runtime-auth-authority.md` | [ADR-0033](../architecture/adr/ADR-0033-single-runtime-auth-authority.md) | Single runtime auth authority |
| `adr/ADR-0002-bearer-jwt-public-auth-contract.md` | [ADR-0034](../architecture/adr/ADR-0034-bearer-jwt-public-auth-contract.md) | Bearer JWT is the only public auth contract |
| `adr/ADR-0003-worker-direct-result-persistence.md` | [ADR-0035](../architecture/adr/ADR-0035-worker-direct-result-persistence.md) | Worker writes results directly |
| `adr/ADR-0004-native-fastapi-contract-expression.md` | [ADR-0036](../architecture/adr/ADR-0036-native-fastapi-openapi-contract.md) | Native FastAPI contract expression |
| `adr/ADR-0005-async-first-public-surface.md` | [ADR-0037](../architecture/adr/ADR-0037-async-first-public-surface.md) | Async-first canonical public surface |
| `adr/ADR-0006-sdk-architecture-by-language.md` | [ADR-0038](../architecture/adr/ADR-0038-sdk-architecture-by-language.md) | SDK architecture by language |
| `adr/ADR-0007-aws-target-platform.md` | [ADR-0039](../architecture/adr/ADR-0039-aws-target-platform.md) | AWS target platform |
| `adr/ADR-0008-repo-rebaseline-after-cuts.md` | [ADR-0040](../architecture/adr/ADR-0040-repo-rebaseline-after-cuts.md) | Rebaseline the repo after architecture cuts |
| `adr/ADR-0009-shared-pure-asgi-middleware-and-errors.md` | [ADR-0041](../architecture/adr/ADR-0041-shared-pure-asgi-middleware-and-errors.md) | Shared pure ASGI middleware and errors |

**Supersedes (when canonical ADRs are active):**

- [ADR-0005](../architecture/adr/superseded/ADR-0005-add-dedicated-nova-auth-api-service.md) (dedicated auth service) → ADR-0033

## SPEC mapping (pack → canonical)

| Pack SPEC | Canonical SPEC | Title |
| --- | --- | --- |
| `spec/SPEC-0001-public-http-api-v2-contract.md` | [SPEC-0027](../architecture/spec/SPEC-0027-public-http-contract-revision-and-bearer-auth.md) | Public HTTP contract revision and bearer auth |
| `spec/SPEC-0002-worker-job-lifecycle.md` | [SPEC-0028](../architecture/spec/SPEC-0028-worker-job-lifecycle-and-direct-result-path.md) | Worker job lifecycle and direct result path |
| `spec/SPEC-0003-sdk-architecture-and-artifact-contract.md` | [SPEC-0029](../architecture/spec/SPEC-0029-sdk-architecture-and-artifact-contract.md) | SDK architecture and artifact contract |

**Naming note:** “Contract revision” in SPEC-0027 refers to **auth and OpenAPI
expression**, not a new URL prefix. Canonical path namespace remains `/v1/*`
per [ADR-0023](../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md).

**Supersedes:**

- [SPEC-0007](../architecture/spec/superseded/SPEC-0007-auth-api-contract.md) (auth API HTTP contract) → SPEC-0027

## Program and evidence

- [greenfield-simplification-program.md](./greenfield-simplification-program.md) -- branch order and DoD
- [greenfield-evidence/README.md](./greenfield-evidence/README.md) -- non-normative audit copies
