# Product Requirements Document (PRD): Nova Runtime

Status: Active canonical PRD
Last updated: 2026-04-02
Audience: Product, Engineering, Platform Operations

## 1. Product goal

Deliver one typed, durable control plane for secure direct-to-S3 transfers and
export workflows, with one canonical serverless runtime and one canonical
release path.

## 2. Desired outcomes

- One canonical public API namespace under `/v1/*` plus `/metrics/summary`.
- One public auth model: bearer JWT only.
- One canonical AWS runtime: Regional REST API, Lambda, Step Functions,
  DynamoDB, S3, CloudWatch, optional non-prod WAF, and production WAF.
- One canonical release executor: AWS-native CodePipeline/CodeBuild after merge.
- One canonical Auth0 automation path using repo-owned template, official
  `auth0-python`, and `auth0-deploy-cli`.
- One canonical documentation authority graph across README, ADR/SPEC,
  contracts, and runbooks.

## 3. Product requirements

1. Nova must remain a control plane, not a byte proxy.
2. Upload/download contracts must continue to target direct S3 data paths.
3. Export creation, status, listing, and cancellation must remain durable and
   explicit under `/v1/exports`.
4. OpenAPI must remain the SDK and client-generation authority.
5. Deploy validation must remain provenance-aware and driven by
   `deploy-output.json`.
6. Runtime and release inputs must remain configurable enough to move the
   system between AWS accounts, Auth0 tenants, and Route 53 zones without
   re-architecting the repo.
7. Operators must be able to reproduce Auth0, release, and runtime operations
   from repo-owned scripts and runbooks without manual one-off shell state.

## 4. Scope

In scope:

- file transfer orchestration
- export workflow orchestration
- generated SDKs and contract artifacts
- AWS runtime and release control plane
- Auth0 tenant automation
- active docs, specs, ADRs, and runbooks

Out of scope:

- session auth or same-origin auth
- generic jobs APIs
- Redis-backed correctness paths
- ECS/Fargate runtime stacks
- CloudFront as compensating API ingress
- split SDK package families

## 5. Success metrics

- Route and contract checks stay green for `/v1/*` plus `/metrics/summary`.
- Generated SDK and contract checks stay green from committed sources.
- Infra contract tests stay green for:
  - AWS-native release control plane
  - execute-api disablement
  - production WAF default
  - non-prod WAF-off default
- Auth0 automation works non-interactively for active tenant overlays.

## 6. Acceptance criteria

1. Active docs describe the implemented AWS-native/Auth0/serverless state.
2. No active docs require deprecated GitHub deploy executors or repo-wide Auth0
   secrets.
3. Runtime deploy inputs and examples stay account-neutral by default.
4. Auth0 bootstrap, audit, import, and export are reproducible from repo-owned
   scripts and matching GitHub workflows.
5. Production browser CORS hardening is explicitly tracked when wildcard CORS
   is used for the first `api-nova` cutover.

## 7. Current tracked exception

- GitHub issue `#111`, `Harden prod CORS origins after initial api-nova cutover`
  tracks removal of the temporary production wildcard CORS allowlist.

## 8. Active references

- `docs/architecture/requirements.md`
- `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `docs/architecture/adr/ADR-0034-eliminate-auth-service-and-session-auth.md`
- `docs/architecture/adr/ADR-0035-replace-generic-jobs-with-export-workflows.md`
- `docs/architecture/adr/ADR-0036-dynamodb-idempotency-no-redis.md`
- `docs/architecture/adr/ADR-0037-sdk-generation-consolidation.md`
- `docs/architecture/adr/ADR-0038-docs-authority-reset.md`
- `docs/architecture/spec/SPEC-0027-public-api-v2.md`
- `docs/architecture/spec/SPEC-0028-export-workflow-state-machine.md`
- `docs/architecture/spec/SPEC-0029-platform-serverless.md`
- `docs/architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `docs/architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`
- `docs/runbooks/release/release-runbook.md`
- `docs/runbooks/release/auth0-a0deploy-runbook.md`
- `infra/nova_cdk/README.md`
