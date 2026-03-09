---
ADR: 0028
Title: Auth0 tenant ops reusable workflow API contract
Status: Accepted
Version: 1.0
Date: 2026-03-04
Related:
  - "[ADR-0025: Reusable GitHub workflow API and versioning policy for deployment automation](./ADR-0025-reusable-workflow-api-and-versioning-policy.md)"
  - "[SPEC-0022: Auth0 tenant ops reusable workflow contract](../spec/SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md)"
  - "[docs/plan/release/AUTH0-A0DEPLOY-RUNBOOK.md](../../plan/release/AUTH0-A0DEPLOY-RUNBOOK.md)"
---

## Summary

Auth0 tenant operations are governed by an explicit reusable workflow API
contract with typed input/output schemas and safety defaults aligned with the
existing tenant-as-code model.

## Context

Auth0 operational guidance exists through runbooks and local validation scripts.
Without a reusable workflow contract, automation behavior can diverge across
repos and environments.

## Decision

1. Auth0 tenant operations adopt a reusable workflow contract as first-class API.
2. Contract schemas under `docs/contracts/**` are source of truth for workflow
   inputs, outputs, and artifact envelope expectations.
3. Safety defaults remain mandatory:
   - `AUTH0_ALLOW_DELETE=false`
   - explicit env overlay + mapping validation before import/export operations.
4. Local CLI and reusable workflow automation must remain behaviorally aligned.

## Consequences

### Positive

- Adds typed, testable automation contract for Auth0 operations.
- Reduces environment-specific shell drift.
- Aligns Auth0 operations with existing reusable workflow governance posture.

### Trade-offs

- Requires schema and docs maintenance for workflow API evolution.
- Increases CI burden for contract synchronization checks.

## Explicit non-decisions

- No direct secret material in repository-tracked workflow inputs.
- No delete-enabled default behavior in automation contracts.

## Changelog

- 2026-03-04: Accepted Auth0 reusable workflow API contract decision.
