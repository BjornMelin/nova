# Nova architecture authority map

Status: Active
Current repository state: **mixed wave-2 implementation with serverless platform components landed**
Last reviewed: 2026-03-25

## Purpose

This router tells you which architecture docs describe:

1. the **current implemented baseline**
2. the **approved target-state program**
3. **historical/superseded** material

Use it before opening any ADR or SPEC.

## State model

### Current implemented baseline

The current repository is in a mixed state: the auth hard cut, export
workflow hard cut, and canonical serverless platform package/IaC components
have landed, while legacy ECS-era deployment assets remain in-tree for older
environments until the final docs/archive cleanup completes.

- public transfer APIs plus explicit export workflows
- bearer JWT only, verified in-process in the main API
- DynamoDB-backed idempotency with explicit expiration filtering
- HTTP API + Lambda Web Adapter + Step Functions Standard as the canonical
  newly landed runtime path
- legacy ECS/Fargate + ALB + SQS worker assets retained only as non-canonical
  migration leftovers

For current reality, use:

- `requirements.md`
- `adr/index.md` -- rows marked `Implemented`
- `spec/index.md` -- rows marked `Implemented`
- current runbooks under `../runbooks/`

### Approved target-state program

The approved wave-2 hard cut defines the future canonical system:

- bearer JWT only
- no auth service
- no session or same-origin public auth
- explicit export workflow resources
- no Redis in the canonical runtime
- API Gateway HTTP API + Lambda Web Adapter + Step Functions Standard
- one SDK package per language
- smaller active docs authority set

For implementation planning and branch work, use:

- `requirements-wave-2.md`
- `adr/ADR-0033-canonical-serverless-platform.md`
- `adr/ADR-0034-eliminate-auth-service-and-session-auth.md`
- `adr/ADR-0035-replace-generic-jobs-with-export-workflows.md`
- `adr/ADR-0036-dynamodb-idempotency-no-redis.md`
- `adr/ADR-0037-sdk-generation-consolidation.md`
- `adr/ADR-0038-docs-authority-reset.md`
- `spec/SPEC-0027-public-api-v2.md`
- `spec/SPEC-0028-export-workflow-state-machine.md`
- `spec/SPEC-0029-platform-serverless.md`
- `spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `spec/SPEC-0031-docs-and-tests-authority-reset.md`

### Historical / superseded

Use only for traceability:

- `adr/superseded/`
- `spec/superseded/`
- `../history/`

### Adjacent implemented baseline governance

These remain the canonical baseline authority for the current deploy/runtime
governance layer while wave-2 target-state implementation is still in progress:

- `adr/ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md`
- `adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md`
- `adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md`
- `spec/SPEC-0024-cloudformation-module-contract.md`
- `spec/SPEC-0025-reusable-workflow-integration-contract.md`
- `spec/SPEC-0026-ci-cd-iam-least-privilege-matrix.md`

## Recommended reading paths

### Operating or validating the current repo

1. `requirements.md`
2. `adr/index.md`
3. `spec/index.md`
4. `../overview/IMPLEMENTATION-STATUS-MATRIX.md`
5. `../runbooks/README.md`

### Implementing the wave-2 hard cut

1. `requirements-wave-2.md`
2. `../overview/CANONICAL-TARGET-2026-04.md`
3. target-state ADRs (`ADR-0033` through `ADR-0038`)
4. target-state SPECs (`SPEC-0027` through `SPEC-0031`)
5. `docs/overview/CANONICAL-TARGET-2026-04.md`
6. `docs/plan/GREENFIELD-WAVE-2-EXECUTION.md`

## Important rule

Older wave-1 green-field drafts were superseded before implementation. If you
see content that assumes bearer-only/export-workflow/serverless was already
implemented, verify it against the status matrix and the new target-state ADR/SPEC set.
