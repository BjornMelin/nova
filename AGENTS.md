# AGENTS.md (nova)

Nova is in a **pre-wave-2** state. This file separates three things that had
become mixed together in the repo docs:

1. the **current implemented baseline**
2. the **approved target-state program**
3. **historical / superseded** material

## Read in order

1. `docs/README.md`
2. `docs/architecture/README.md`
3. `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
4. `README.md`
5. `docs/standards/README.md`
6. `docs/runbooks/README.md` for live operations
7. `.agents/AUDIT_DELIVERABLES/README_RUN_ORDER.md` for implementation work

## State model

### Current implemented baseline

Use this when operating, debugging, or validating the repository **before**
the wave-2 branches are implemented and merged.

Baseline examples:

- ECS/Fargate + ALB + SQS worker remains the documented deployed shape
- dedicated auth-service-era artifacts still exist
- generic jobs remain part of the public async contract
- Redis still appears in correctness paths
- split SDK/package layout still exists

### Approved target-state program

Use this when planning or implementing the hard-cut modernization branches.

Target-state authority:

- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `docs/architecture/adr/ADR-0034-eliminate-auth-service-and-session-auth.md`
- `docs/architecture/adr/ADR-0035-replace-generic-jobs-with-export-workflows.md`
- `docs/architecture/adr/ADR-0036-dynamodb-idempotency-no-redis.md`
- `docs/architecture/adr/ADR-0037-sdk-generation-consolidation.md`
- `docs/architecture/adr/ADR-0038-docs-authority-reset.md`
- `docs/architecture/spec/SPEC-0027-public-api-v2.md`
- `docs/architecture/spec/SPEC-0028-export-workflow-state-machine.md`
- `docs/architecture/spec/SPEC-0029-platform-serverless.md`
- `docs/architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `docs/architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`
- `docs/plan/GREENFIELD-WAVE-2-EXECUTION.md`
- `.agents/AUDIT_DELIVERABLES/prompts/*`

### Historical / superseded

Never treat these as active authority:

- `docs/history/**`
- `docs/architecture/adr/superseded/**`
- `docs/architecture/spec/superseded/**`

## Core laws

- Do not mix current-baseline facts and target-state decisions in the same
  implementation note without naming which state you mean.
- When implementing branches, the target-state ADR/SPEC set wins over older
  wave-1 drafts.
- When operating current environments, the existing provisioning/release
  runbooks win until the migration actually lands.
- Do not resurrect session auth, remote auth verification services, generic
  public jobs, Redis-backed correctness paths, or bespoke TS runtime glue.

## Prompt execution

When using Codex or another implementation agent:

1. open `.agents/AUDIT_DELIVERABLES/README_RUN_ORDER.md`
2. open `.agents/AUDIT_DELIVERABLES/EXECUTIVE_AUDIT_V2.md`
3. open the prompt for the current branch
4. use `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md` to confirm the delta
5. use `docs/architecture/spec/REFERENCES.md` for official external references

## Documentation update rule

If you change code, contracts, package layout, or platform shape in a branch,
update the corresponding active current/target docs in the same branch. Keep
status and implementation-state language accurate.
