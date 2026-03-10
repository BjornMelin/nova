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

1. Reusable workflows are published as versioned external automation APIs.
2. Supported cross-repo refs are:
   - stable moving major tags such as `@v1`
   - immutable release tags such as `@v1.x.y`
   - full commit SHAs
3. Production and high-assurance consumers MUST pin immutable release tags or
   full commit SHAs.
4. Consumer docs MUST NOT publish branch refs such as `@main` as supported
   integration references.
5. Breaking caller-visible workflow contract changes require a new major tag
   and synchronized contract-doc updates.

## 6. Consumer integration contract

1. Reusable workflows that invoke internal composite actions from
   `.github/actions/**` must checkout their workflow source repository at the
   immutable `github.workflow_sha` revision before using local actions.
2. Downstream examples under `docs/clients/**` must compile and reference
   reusable workflows.
3. Validation workflows require `NOVA_API_BASE_URL` and must produce
   contract-compliant artifacts.
4. Integration guides may use `@v1` in prose quick starts, but committed
   examples must use immutable release tags and production guidance must
   require immutable refs.
5. Composite actions under `.github/actions/**` remain internal implementation
   details and are not a supported external API surface.

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
