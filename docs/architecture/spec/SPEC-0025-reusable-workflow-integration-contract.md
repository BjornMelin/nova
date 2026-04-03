---
Spec: 0025
Title: Reusable workflow integration contract
Status: Active
Version: 1.3
Date: 2026-04-02
Supersedes: "[SPEC-0018 (superseded): Reusable workflow integration contract](./superseded/SPEC-0018-reusable-workflow-integration-contract.md)"
Related:
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](../adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
  - "[ADR-0028: Auth0 tenant ops reusable workflow API contract](../adr/ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md)"
  - "[SPEC-0021: Downstream hard-cut integration and consumer validation contract](./SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md)"
  - "[SPEC-0022: Auth0 tenant ops reusable workflow contract](./SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md)"
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
2. `reusable-post-deploy-validate.yml`
3. `reusable-auth0-tenant-deploy.yml`

## 3. Wrapper workflow contract

1. Entry workflows are wrapper-only and delegate execution to reusable
   workflows.
2. Wrapper workflows must not reimplement deployment business logic.
3. Shared logic belongs to composite actions under `.github/actions/**`.

## 4. Typed input/output contract

1. Reusable workflows must declare typed `workflow_call` inputs/outputs.
2. Contract schemas are source-of-truth artifacts in:
   - `docs/contracts/deploy-output-authority-v2.schema.json`
   - `docs/contracts/workflow-post-deploy-validate.schema.json`
   - `docs/contracts/workflow-auth0-tenant-deploy.schema.json`
   - `docs/contracts/release-prep-v1.schema.json`
   - `docs/contracts/release-execution-manifest-v1.schema.json`
3. The AWS-native release control plane emits `deploy-output.json` and
   `deploy-output.sha256` as the authoritative deployment evidence.

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
3. Validation workflows must resolve their base URL from an authoritative
   deploy-output artifact or a direct reference to that artifact, and must
   produce contract-compliant artifacts.
4. Integration guides may use `@v1` in prose quick starts, but committed
   examples must use immutable release tags and production guidance must
   require immutable refs.
5. Composite actions under `.github/actions/**` remain internal implementation
   details and are not a supported external API surface.

## 7. Deploy-output authority contract

The surviving reusable validation API MUST:

1. accept deploy-output authority via one of:
   - `deploy_run_id`
   - `deploy_output_json`
   - `deploy_output_path`
2. make validation consume that deploy-output artifact instead of a free-text
   URL input
3. preserve `deploy-output.json` plus `deploy-output.sha256` as the authority
   contract created by the AWS-native release control plane
4. default the downloaded artifact name to `deploy-output`

## 8. Acceptance criteria

1. Workflow/productization contract tests pass.
2. Contract docs tests assert schema/workflow parity.
3. Actionlint passes for all workflow files.
4. Reusable validation docs align with the live deploy-output authority contract.

## 9. Traceability

- [NFR-0105](../requirements.md#nfr-0105-contract-traceability)
- [NFR-0106](../requirements.md#nfr-0106-no-shim-posture)
- [IR-0000](../requirements.md#ir-0000-nova-local-runtime-and-release-authority)
