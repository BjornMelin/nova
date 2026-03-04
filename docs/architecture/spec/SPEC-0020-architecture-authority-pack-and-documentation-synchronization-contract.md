---
Spec: 0020
Title: Rollout and validation strategy
Status: Active
Version: 1.1
Date: 2026-03-03
Related:
  - "[ADR-0024: Native-CFN modular stack architecture for Nova infrastructure productization](../adr/ADR-0024-layered-architecture-authority-pack.md)"
  - "[ADR-0026: OIDC and IAM role partitioning for deploy automation](../adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)"
  - "[SPEC-0017: CloudFormation module contract](./SPEC-0017-runtime-component-topology-and-ownership-contract.md)"
  - "[SPEC-0018: Reusable workflow integration contract](./SPEC-0018-runtime-configuration-and-startup-validation-contract.md)"
  - "[SPEC-0019: CI/CD IAM least-privilege matrix](./SPEC-0019-auth-execution-and-threadpool-safety-contract.md)"
---

## 1. Scope

Defines rollout sequencing, validation gates, and acceptance criteria for Nova
infrastructure productization and reusable deployment APIs.

## 2. Rollout order (required)

Stacks and control-plane components must be applied in this order:

1. Foundation (`nova-foundation`)
2. IAM roles (`nova-iam-roles`)
3. CodeBuild release projects (`nova-codebuild-release`)
4. CI/CD pipeline (`nova-ci-cd`)
5. Runtime stacks (`nova-dev` / `nova-prod`)

## 3. Deployment execution strategy

1. Use change-set-first stack updates.
2. Require explicit approval for production promotion paths.
3. Capture deploy evidence artifacts for each run.

## 4. Validation gates

| Gate | Purpose | Required evidence |
| --- | --- | --- |
| A | Identity and account readiness | `sts get-caller-identity`, stack read access |
| B | Control-plane readiness | CI/CD stack healthy, pipeline contract matches template |
| C | Runtime inventory | ECS/CodeDeploy/alarms inventory present as expected |
| D | Route and behavior validation | Post-deploy route checks and canonical/legacy assertions |
| E | Release acceptance | Artifacts, approvals, and runbook checklist closure |

## 5. Failure and recovery requirements

1. `UPDATE_ROLLBACK_FAILED` stacks must be recovered before progressing.
2. IAM access-denied blockers are release blockers until remediated.
3. Recoveries must preserve IaC source-of-truth (no unmanaged hotfix drift).

## 6. Documentation and ledger synchronization

1. The active orchestration plan file under `.agents/plans/` is the shared
   execution ledger for status, subagents, and verification evidence.
2. Checklist state must reflect implemented + verified vs blocked items.
3. All blockers require explicit action/resource evidence and remediation steps.

## 7. Acceptance criteria

1. Rollout order is executed successfully end-to-end.
2. Gates A-E are satisfied with evidence captured in release docs/ledger.
3. Reusable workflow contracts and infra tests pass in CI.

## 8. Traceability

- [NFR-0105](../requirements.md#nfr-0105-contract-traceability)
- [NFR-0106](../requirements.md#nfr-0106-no-shim-posture)
- [IR-0000](../requirements.md#ir-0000-nova-local-runtime-and-release-authority)
