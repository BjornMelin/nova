---
Spec: 0025
Title: Reusable workflow integration contract
Status: Active
Version: 1.1
Date: 2026-03-05
Related:
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](../adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
  - "[ADR-0028: Auth0 tenant ops reusable workflow API contract](../adr/ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md)"
  - "[SPEC-0021: Downstream hard-cut integration and consumer validation contract](./SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md)"
  - "[SPEC-0022: Auth0 tenant ops reusable workflow contract](./SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md)"
  - "[SPEC-0023: SSM runtime base-url contract for deploy validation](./SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md)"
  - "[SPEC-0004: CI/CD and documentation automation](./SPEC-0004-ci-cd-and-docs.md)"
References:
  - "[Validate stack deployments](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/validate-stack-deployments.html)"
  - "[DescribeEvents](https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_DescribeEvents.html)"
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
8. `reusable-auth0-tenant-deploy.yml`

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
   - `docs/contracts/workflow-auth0-tenant-deploy.schema.json`
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

## 7. CloudFormation validation contract

Reusable deployment APIs that create or update CloudFormation change sets MUST
document and preserve the current validation flow:

1. create or update a change set first
2. inspect validation results with
   `aws cloudformation describe-events --stack-name ... --change-set-name ...`
3. read validation output from `OperationEvents`
4. treat `FAIL` validation results as execute-blocking and `WARN` results as
   reviewable non-blocking findings

## 8. Acceptance criteria

1. Workflow/productization contract tests pass.
2. Contract docs tests assert schema/workflow parity.
3. Actionlint passes for all workflow files.
4. Reusable deploy docs align with the live `DescribeEvents` and
   `OperationEvents` validation contract.

## 9. Traceability

- [NFR-0105](../requirements.md#nfr-0105-contract-traceability)
- [NFR-0106](../requirements.md#nfr-0106-no-shim-posture)
- [IR-0000](../requirements.md#ir-0000-nova-local-runtime-and-release-authority)
