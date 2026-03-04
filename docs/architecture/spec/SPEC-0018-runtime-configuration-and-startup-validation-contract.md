---
Spec: 0018
Title: Reusable workflow integration contract
Status: Active
Version: 1.1
Date: 2026-03-03
Related:
  - "[ADR-0025: Reusable GitHub workflow API and versioning policy for deployment automation](../adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md)"
  - "[SPEC-0017: CloudFormation module contract](./SPEC-0017-runtime-component-topology-and-ownership-contract.md)"
  - "[SPEC-0004: CI/CD and documentation automation](./SPEC-0004-ci-cd-and-docs.md)"
---

## 1. Scope

Defines reusable GitHub workflow APIs, typed input/output contracts, and
integration guarantees for Nova and downstream repos.

## 2. Reusable workflow API surface

Required reusable workflows:

1. `reusable-release-plan.yml`
2. `reusable-release-apply.yml`
3. `reusable-bootstrap-foundation.yml`
4. `reusable-deploy-runtime.yml`
5. `reusable-deploy-dev.yml`
6. `reusable-promote-prod.yml`
7. `reusable-post-deploy-validate.yml`

## 3. Wrapper workflow contract

1. Entry workflows are wrapper-only and delegate execution to reusable
   workflows.
2. Wrapper workflows must not reimplement deployment business logic.
3. Shared logic belongs to composite actions under `.github/actions/**`.

## 4. Typed input/output contract

1. Reusable workflows must declare typed `workflow_call` inputs/outputs.
2. Contract schemas are source-of-truth artifacts in:
   - `docs/contracts/reusable-workflow-inputs-v1.schema.json`
   - `docs/contracts/reusable-workflow-outputs-v1.schema.json`
   - `docs/contracts/workflow-post-deploy-validate.schema.json`
3. Runtime deploy contract includes size profiles and custom bounds validation.

## 5. Versioning policy

1. `@v1` is the stable compatibility channel.
2. `@v1.x.y` tags are immutable and required for production pinning.
3. Breaking contract changes require a new major channel (`v2`, etc.).

## 6. Consumer integration contract

1. Downstream examples under `docs/clients/**` must compile and reference
   reusable workflows.
2. Validation workflows require `NOVA_API_BASE_URL` and must produce
   contract-compliant artifacts.
3. Integration guides must document both stable and immutable pin strategies.

## 7. Acceptance criteria

1. Workflow/productization contract tests pass.
2. Contract docs tests assert schema/workflow parity.
3. Actionlint passes for all workflow files.

## 8. Traceability

- [NFR-0105](../requirements.md#nfr-0105-contract-traceability)
- [NFR-0106](../requirements.md#nfr-0106-no-shim-posture)
- [IR-0000](../requirements.md#ir-0000-nova-local-runtime-and-release-authority)
