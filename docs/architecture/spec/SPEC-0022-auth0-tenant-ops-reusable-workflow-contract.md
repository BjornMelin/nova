---
Spec: 0022
Title: Auth0 tenant ops reusable workflow contract
Status: Active
Version: 1.0
Date: 2026-03-04
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[ADR-0028: Auth0 tenant ops reusable workflow API contract](../adr/ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md)"
  - "[SPEC-0025: Reusable workflow integration contract](./SPEC-0025-reusable-workflow-integration-contract.md)"
  - "[docs/runbooks/release/auth0-a0deploy-runbook.md](../../runbooks/release/auth0-a0deploy-runbook.md)"
---

## 1. Scope

Defines reusable workflow contract requirements for Auth0 tenant operations and
its synchronization with existing tenant-as-code runbook and validator controls.

## 2. Contract authority artifacts

1. Reusable workflow contract schema:
   - `docs/contracts/workflow-auth0-tenant-ops-v1.schema.json`
2. Auth0 runbook authority:
   - `docs/runbooks/release/auth0-a0deploy-runbook.md`
3. Local validation authority:
   - `scripts/release/validate_auth0_contract.py`

## 3. Workflow API requirements

1. Auth0 reusable workflow APIs MUST use typed input/output contracts.
2. Inputs MUST include explicit operation mode and environment targeting.
3. Outputs MUST include explicit operation status and artifact references.
4. Workflow contracts MUST preserve safety defaults and fail fast when contracts
   are invalid.

## 4. Safety contract

1. `AUTH0_ALLOW_DELETE=false` remains mandatory default.
2. Overlay + mapping contract validation is required before bootstrap, audit,
   import, and export actions.
3. Reusable workflow mutation/reporting steps (`bootstrap`, `audit`, `import`,
   `export`)
   MUST be gated on successful contract validation and MUST NOT execute when
   validation fails.
4. Audit MUST fail closed on repo-template drift. A successful audit means the
   live tenant matched the expected Nova resource server, expected clients, and
   the tenant-ops grant for the Nova API audience.
5. Local CLI wrappers MUST re-enforce the non-destructive env contract at
   runtime before invoking `auth0-deploy-cli`; tracked examples are not the
   only safety boundary.
6. Credential material must not be stored in repository-tracked files.
7. Hosted workflow credentials must come from environment-scoped GitHub
   secrets (`auth0-dev`, `auth0-pr`, `auth0-qa`), not repo-wide Auth0
   secrets.

## 5. Synchronization contract

1. Auth0 workflow contract changes require synchronized updates to:
   - runbook docs,
   - schema docs/contracts, and
   - contract tests.
2. Drift between runbook/local validator/workflow API is release-blocking.

## 6. Acceptance criteria

1. Auth0 contract schema exists and validates as JSON schema.
2. Runbook references reusable workflow contract artifacts.
3. Contract tests assert schema + runbook + validator linkage.

## 7. Traceability

- [FR-0012](../requirements.md#fr-0012-auth0-tenant-ops-reusable-workflow-contract)
- [NFR-0108](../requirements.md#nfr-0108-auth0-workflow-contract-synchronization)
- [IR-0012](../requirements.md#ir-0012-auth0-tenant-ops-authority-boundary)
