---
Spec: 0020
Title: Architecture authority pack and documentation synchronization contract
Status: Active
Version: 2.0
Date: 2026-03-05
Related:
  - "[ADR-0024: Layered runtime authority pack for the Nova monorepo](../adr/ADR-0024-layered-architecture-authority-pack.md)"
  - "[ADR-0030: Native-CFN modular stack architecture for Nova infrastructure productization](../adr/ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md)"
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](../adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](../adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
  - "[SPEC-0015: Nova API platform final topology and delivery contract](./SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md)"
  - "[SPEC-0024: CloudFormation module contract](./SPEC-0024-cloudformation-module-contract.md)"
  - "[SPEC-0025: Reusable workflow integration contract](./SPEC-0025-reusable-workflow-integration-contract.md)"
  - "[SPEC-0026: CI/CD IAM least-privilege matrix](./SPEC-0026-ci-cd-iam-least-privilege-matrix.md)"
---

## 1. Scope

Defines how Nova classifies architecture authority documents, synchronizes
active authority references, and archives superseded ADR/SPEC material without
leaving conflicting active guidance behind.

## 2. Authority classes

Nova architecture documents are divided into three classes:

1. Active runtime authority
   - `docs/PRD.md`
   - `docs/architecture/requirements.md`
   - `ADR-0023` through `ADR-0029`
   - `SPEC-0000`
   - `SPEC-0015` through `SPEC-0023`
   - `docs/plan/PLAN.md`
   - `docs/runbooks/README.md`
2. Adjacent deploy-governance authority
   - `ADR-0030` through `ADR-0032`
   - `SPEC-0024` through `SPEC-0026`
3. Superseded authority
   - `docs/architecture/adr/superseded/**`
   - `docs/architecture/spec/superseded/**`
   - superseded material is preserved for traceability only and is not active
     authority

## 3. Synchronization contract

When architecture, deploy-governance, or runtime contracts change, the same
change set MUST update all affected active authority surfaces:

1. `AGENTS.md`
2. `docs/PRD.md`
3. `docs/architecture/requirements.md`
4. `docs/architecture/adr/index.md`
5. `docs/architecture/spec/index.md`
6. `docs/plan/PLAN.md`
7. `docs/runbooks/README.md`
8. affected ADR/SPEC files
9. affected `docs/plan/release/**` and `docs/contracts/**` files when deploy
   or reusable workflow contracts change

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
5. WAF rate-based protections on public ALB ingress

## 6. Testable invariants

1. `AGENTS.md`, `docs/PRD.md`, `docs/plan/PLAN.md`, and
   `docs/runbooks/README.md` must reference the same active authority set.
2. `docs/architecture/adr/index.md` and `docs/architecture/spec/index.md` must
   separate active and superseded sections.
3. Active architecture docs must not use `.agents/plans/` as an execution
   ledger authority.
4. Active architecture docs must not leave stale subject/title mismatches
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
