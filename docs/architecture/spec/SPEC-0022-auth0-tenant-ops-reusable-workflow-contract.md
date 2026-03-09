---
Spec: 0022
Title: Auth0 tenant ops reusable workflow contract
Status: Active
Version: 1.0
Date: 2026-03-04
Related:
  - "[ADR-0028: Auth0 tenant ops reusable workflow API contract](../adr/ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md)"
  - "[SPEC-0018: Reusable workflow integration contract](./SPEC-0018-runtime-configuration-and-startup-validation-contract.md)"
  - "[docs/plan/release/AUTH0-A0DEPLOY-RUNBOOK.md](../../plan/release/AUTH0-A0DEPLOY-RUNBOOK.md)"
---

## 1. Scope

Defines reusable workflow contract requirements for Auth0 tenant operations and
its synchronization with existing tenant-as-code runbook and validator controls.

## 2. Contract authority artifacts

1. Reusable workflow contract schema:
   - `docs/contracts/workflow-auth0-tenant-ops-v1.schema.json`
2. Auth0 runbook authority:
   - `docs/plan/release/AUTH0-A0DEPLOY-RUNBOOK.md`
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
2. Overlay + mapping contract validation is required before import/export
   actions.
3. Reusable workflow mutation steps (`import`, `export`, tool installation)
   MUST be gated on successful contract validation and MUST NOT execute when
   validation fails.
4. Credential material must not be stored in repository-tracked files.

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
