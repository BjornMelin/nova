---
Spec: 0020
Title: Architecture authority pack and documentation synchronization contract
Status: Superseded
Superseded-by: "[SPEC-0031: Docs and tests authority reset](../SPEC-0031-docs-and-tests-authority-reset.md)"
Version: 2.1
Date: 2026-03-24
Related:
  - "[ADR-0024: Layered runtime authority pack for the Nova monorepo](../../adr/ADR-0024-layered-architecture-authority-pack.md)"
  - "[ADR-0030: Native-CFN modular stack architecture for Nova infrastructure productization](../../adr/superseded/ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md)"
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](../../adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](../../adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
  - "[SPEC-0015: Nova API platform final topology and delivery contract](./SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md)"
  - "[SPEC-0024: CloudFormation module contract](../SPEC-0024-cloudformation-module-contract.md)"
  - "[SPEC-0025: Reusable workflow integration contract](../SPEC-0025-reusable-workflow-integration-contract.md)"
  - "[SPEC-0026: CI/CD IAM least-privilege matrix](../SPEC-0026-ci-cd-iam-least-privilege-matrix.md)"
---

## 1. Scope

Defines how Nova classifies architecture authority documents, synchronizes
active authority references, and archives superseded ADR/SPEC material without
leaving conflicting active guidance behind.

## 2. Authority classes

Nova architecture and operator guidance is divided into four classes:

1. Active narrative router authority
   - `AGENTS.md`
   - `README.md`
   - `docs/README.md`
   - `docs/architecture/README.md`
   - `docs/standards/README.md`
   - `docs/standards/repository-engineering-standards.md`
   - `docs/runbooks/README.md`
   - `docs/contracts/README.md`
   - `docs/plan/PLAN.md`
2. Active runtime, SDK, and repository-governance authority
   - `docs/PRD.md`
   - `docs/architecture/requirements.md`
   - `ADR-0023` through `ADR-0029`
   - `ADR-0033` through `ADR-0041`
   - `SPEC-0000`
   - `SPEC-0004`
   - `SPEC-0012`
   - `SPEC-0015` through `SPEC-0022`
   - `SPEC-0027` through `SPEC-0029`
3. Adjacent deploy-governance authority
   - `ADR-0030` through `ADR-0032`
   - `SPEC-0024` through `SPEC-0026`
4. Superseded authority
   - `docs/architecture/adr/superseded/**`
   - `docs/architecture/spec/superseded/**`
   - superseded material is preserved for traceability only and is not active
     authority

## 3. Synchronization contract

When architecture, deploy-governance, or runtime contracts change, the same
change set MUST update all affected active authority surfaces (including
green-field program steps, where implementation PRs MUST land docs updates
together with code per branch merge policy):

1. `AGENTS.md`
2. `README.md`
3. `docs/README.md`
4. `docs/PRD.md`
5. `docs/architecture/README.md`
6. `docs/architecture/requirements.md`
7. `docs/standards/README.md`
8. `docs/standards/repository-engineering-standards.md`
9. `docs/contracts/README.md`
10. `docs/architecture/adr/index.md`
11. `docs/architecture/spec/index.md`
12. `docs/plan/PLAN.md`
13. `docs/runbooks/README.md`
14. affected ADR/SPEC files
15. affected `docs/runbooks/**`, committed `docs/release/**`,
    `docs/contracts/**`, and `docs/clients/**` files when deploy, workflow,
    SDK, or reusable workflow contracts change

## 4. Superseded-material contract

1. Superseded ADRs and SPECs MUST be moved under the dedicated
   `superseded/` directories.
2. Superseded ADRs and SPECs MUST declare the active replacement or governing
   authority set in the archived file.
3. Active authority lists and active index sections MUST NOT reference files in
   `superseded/`.
4. Historical execution evidence belongs under `docs/history/**`, not under
   active architecture identifiers.

## 5. Deploy-governance citation contract

Active deploy-governance docs MUST remain aligned to current official AWS
documentation for the live implementation. The primary authority document for a
subject must cite the relevant AWS source when it describes:

1. ECS-native blue/green deployment behavior
2. ECS infrastructure IAM role requirements for load balancer traffic shifting
3. CloudFormation pre-deployment validation via change sets and
   `DescribeEvents`
4. `OperationEvents` validation output semantics
5. [HISTORICAL] WAF rate-based protections on the public regional REST API
   ingress and the direct Lambda-backed control-plane model behind it

## 6. Testable invariants

1. `AGENTS.md`, `README.md`, `docs/README.md`,
   `docs/architecture/README.md`, `docs/standards/README.md`,
   `docs/plan/PLAN.md`, and `docs/runbooks/README.md` must reference the same
   active authority set.
2. `docs/architecture/adr/index.md` and `docs/architecture/spec/index.md` must
   separate active and superseded sections.
3. Active authority lists and active index sections must not reference
   `superseded/` paths as current SDK or runtime authority.
4. Active architecture docs must not use `.agents/plans/` as an execution
   ledger authority.
5. Active architecture docs must not leave stale subject/title mismatches
   between filename, title, and referenced purpose.

## 7. Acceptance criteria

1. Active authority references are self-consistent across top-level docs.
2. Superseded ADR/SPEC files are physically separated and excluded from active
   sections.
3. Deploy-governance docs cite current AWS sources that match the live Nova
   deployment model.
4. Documentation contract tests fail when active references drift from this
   structure.

## 8. Traceability

- [NFR-0105](../requirements.md#nfr-0105-contract-traceability)
- [NFR-0110](../requirements.md#nfr-0110-architecture-authority-synchronization)
- [IR-0014](../requirements.md#ir-0014-superseded-architecture-archive-boundary)
